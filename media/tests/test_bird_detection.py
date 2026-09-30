from io import BytesIO
from unittest.mock import patch

import numpy as np
from django.test import TestCase, override_settings
from PIL import Image

from jizz.models import Species
from media.bird_detection import (
    bird_detection_status,
    decode_image_bytes,
    detect_birds_for_queryset,
)
from media.first_assertion.feature_extraction.yolo import (
    YoloBirdResult,
    _postprocess_yolov5_style,
)
from media.models import Media, MediaBirdDetection


class BirdDetectionDecisionTestCase(TestCase):
    def test_detected_box_is_bird(self):
        result = YoloBirdResult(0.75, 1, 0.2)
        self.assertEqual(
            bird_detection_status(result, no_bird_threshold=0.05),
            MediaBirdDetection.BIRD,
        )

    def test_very_low_score_is_no_bird(self):
        result = YoloBirdResult(0.01, 0, 0.0)
        self.assertEqual(
            bird_detection_status(result, no_bird_threshold=0.05),
            MediaBirdDetection.NO_BIRD,
        )

    def test_score_between_thresholds_is_uncertain(self):
        result = YoloBirdResult(0.10, 0, 0.0)
        self.assertEqual(
            bird_detection_status(result, no_bird_threshold=0.05),
            MediaBirdDetection.UNCERTAIN,
        )

    def test_decode_applies_size_bound(self):
        image = Image.new('RGB', (2400, 1200), 'white')
        buffer = BytesIO()
        image.save(buffer, format='JPEG')
        decoded = decode_image_bytes(buffer.getvalue(), max_side=600)
        self.assertEqual(decoded.shape, (300, 600, 3))


class YoloPostprocessingTestCase(TestCase):
    def test_yolov5_detection_returns_box_area(self):
        detection = np.zeros((1, 1, 85), dtype=np.float32)
        detection[0, 0, :4] = [320, 320, 320, 320]
        detection[0, 0, 4] = 1.0
        detection[0, 0, 5 + 14] = 0.9

        result = _postprocess_yolov5_style(
            detection,
            conf_thr=0.25,
            iou_thr=0.45,
            bird_id=14,
            rgb_u8=np.zeros((640, 640, 3), dtype=np.uint8),
            scale=1.0,
            pad_x=0,
            pad_y=0,
        )

        self.assertEqual(result.bird_num_boxes, 1)
        self.assertAlmostEqual(result.bird_max_conf, 0.9, places=5)
        self.assertAlmostEqual(result.bird_max_area_ratio, 0.25, places=5)


@override_settings(
    MEDIA_YOLO_MODEL_VERSION='test-yolo',
    MEDIA_YOLO_NO_BIRD_THRESHOLD=0.05,
    MEDIA_YOLO_CONF_THRESHOLD=0.25,
)
class BirdDetectionRunTestCase(TestCase):
    def setUp(self):
        species = Species.objects.create(name='Test bird', name_latin='Avis test', code='tstbir')
        self.media = Media.objects.create(
            species=species,
            type='image',
            url='https://example.com/bird.jpg',
        )

    @patch('media.bird_detection.yolo_bird_features')
    @patch('media.bird_detection.decode_image_bytes')
    @patch('media.bird_detection.download_image')
    def test_upserts_detection(self, download, decode, detect):
        download.return_value = (b'image', 5)
        decode.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        detect.return_value = YoloBirdResult(0.8, 2, 0.4)

        stats = detect_birds_for_queryset(Media.objects.all())

        self.assertEqual(stats.bird, 1)
        row = MediaBirdDetection.objects.get(media=self.media)
        self.assertEqual(row.status, MediaBirdDetection.BIRD)
        self.assertEqual(row.detector_version, 'test-yolo')
        self.assertEqual(row.bird_box_count, 2)

    @patch('media.bird_detection.yolo_bird_features')
    @patch('media.bird_detection.decode_image_bytes')
    @patch('media.bird_detection.download_image')
    def test_updates_existing_detection_in_bulk(self, download, decode, detect):
        MediaBirdDetection.objects.create(
            media=self.media,
            status=MediaBirdDetection.NO_BIRD,
            bird_confidence=0.01,
            detector_version='old-yolo',
        )
        download.return_value = (b'image', 5)
        decode.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        detect.return_value = YoloBirdResult(0.8, 1, 0.4)

        detect_birds_for_queryset(Media.objects.all())

        row = MediaBirdDetection.objects.get(media=self.media)
        self.assertEqual(row.status, MediaBirdDetection.BIRD)
        self.assertEqual(row.detector_version, 'test-yolo')

    @patch('media.bird_detection.download_image', side_effect=RuntimeError('network'))
    def test_failure_is_left_missing_for_retry(self, _download):
        stats = detect_birds_for_queryset(Media.objects.all())
        self.assertEqual(stats.failed, 1)
        self.assertFalse(MediaBirdDetection.objects.exists())

    @patch('media.bird_detection.yolo_bird_features')
    @patch('media.bird_detection.decode_image_bytes')
    @patch('media.bird_detection.download_image')
    def test_dry_run_does_not_write(self, download, decode, detect):
        download.return_value = (b'image', 5)
        decode.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        detect.return_value = YoloBirdResult(0.01, 0, 0.0)

        stats = detect_birds_for_queryset(Media.objects.all(), dry_run=True)

        self.assertEqual(stats.no_bird, 1)
        self.assertFalse(MediaBirdDetection.objects.exists())
