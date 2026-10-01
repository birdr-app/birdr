"""Conservative YOLO bird-presence triage for Birdr image media."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import numpy as np
from django.conf import settings
from django.db.models import QuerySet
from PIL import Image, ImageOps

from media.first_assertion.feature_extraction.yolo import YoloBirdResult, yolo_bird_features
from media.first_assertion.features import download_image
from media.models import MediaBirdDetection

logger = logging.getLogger(__name__)
WRITE_BATCH_SIZE = 100


@dataclass(frozen=True)
class BirdDetectionRunStats:
    processed: int = 0
    bird: int = 0
    no_bird: int = 0
    uncertain: int = 0
    failed: int = 0


def decode_image_bytes(data: bytes, *, max_side: int = 1280) -> np.ndarray:
    """Decode, orient and bound an image before YOLO letterboxing."""
    with Image.open(BytesIO(data)) as opened:
        image = ImageOps.exif_transpose(opened)
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if image.mode in ('RGBA', 'LA') or 'transparency' in (image.info or {}):
            rgba = image.convert('RGBA')
            background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba).convert('RGB')
        else:
            image = image.convert('RGB')
        return np.asarray(image, dtype=np.uint8)


def bird_detection_status(
    result: YoloBirdResult,
    *,
    no_bird_threshold: float,
) -> str:
    """Map detector output to a safe three-way triage decision."""
    if result.bird_num_boxes > 0:
        return MediaBirdDetection.BIRD
    if result.bird_max_conf < no_bird_threshold:
        return MediaBirdDetection.NO_BIRD
    return MediaBirdDetection.UNCERTAIN


def detect_birds_for_queryset(
    qs: QuerySet,
    *,
    detector_version: Optional[str] = None,
    no_bird_threshold: Optional[float] = None,
    dry_run: bool = False,
    progress_every: int = 0,
) -> BirdDetectionRunStats:
    """Download images, run YOLO and upsert bird-presence results.

    Download/decode/inference failures deliberately create no row, allowing a
    later ``--only-missing`` run to retry them.
    """
    version = detector_version or settings.MEDIA_YOLO_MODEL_VERSION
    threshold = (
        float(no_bird_threshold)
        if no_bird_threshold is not None
        else float(settings.MEDIA_YOLO_NO_BIRD_THRESHOLD)
    )
    if not 0.0 <= threshold <= float(settings.MEDIA_YOLO_CONF_THRESHOLD):
        raise ValueError(
            'no_bird_threshold must be between 0 and MEDIA_YOLO_CONF_THRESHOLD'
        )

    counts = {
        MediaBirdDetection.BIRD: 0,
        MediaBirdDetection.NO_BIRD: 0,
        MediaBirdDetection.UNCERTAIN: 0,
    }
    processed = failed = 0
    pending: list[MediaBirdDetection] = []

    def flush_pending() -> None:
        if dry_run or not pending:
            return
        MediaBirdDetection.objects.bulk_create(
            pending,
            batch_size=WRITE_BATCH_SIZE,
            update_conflicts=True,
            update_fields=[
                'status',
                'bird_confidence',
                'bird_box_count',
                'bird_max_area_ratio',
                'detector_version',
                'updated',
            ],
            unique_fields=['media'],
        )
        pending.clear()

    # Commands order before applying a limit. Preserve an already sliced
    # queryset because Django cannot add ordering after slicing.
    if not qs.ordered and not qs.query.is_sliced:
        qs = qs.order_by('id')

    for media in qs.iterator(chunk_size=50):
        try:
            data, _size = download_image(media.url)
            rgb = decode_image_bytes(data)
            result = yolo_bird_features(rgb)
            status = bird_detection_status(result, no_bird_threshold=threshold)
        except Exception as exc:
            logger.warning('Bird detection failed for media %s: %s', media.id, exc)
            failed += 1
            continue

        if not dry_run:
            pending.append(
                MediaBirdDetection(
                    media_id=media.id,
                    status=status,
                    bird_confidence=result.bird_max_conf,
                    bird_box_count=result.bird_num_boxes,
                    bird_max_area_ratio=result.bird_max_area_ratio,
                    detector_version=version,
                )
            )
            if len(pending) >= WRITE_BATCH_SIZE:
                flush_pending()
        processed += 1
        counts[status] += 1

        total = processed + failed
        if progress_every and total % progress_every == 0:
            logger.info(
                'Bird detection progress: %s attempted (processed=%s, failed=%s)',
                total,
                processed,
                failed,
            )

    flush_pending()

    return BirdDetectionRunStats(
        processed=processed,
        bird=counts[MediaBirdDetection.BIRD],
        no_bird=counts[MediaBirdDetection.NO_BIRD],
        uncertain=counts[MediaBirdDetection.UNCERTAIN],
        failed=failed,
    )
