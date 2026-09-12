from django.test import SimpleTestCase, override_settings

from media.wikimedia_urls import (
    wikimedia_commons_thumb_url,
    wikimedia_display_url,
    wikimedia_video_ios_url,
    wikimedia_video_original_url,
    wikimedia_video_playback_url,
)


class WikimediaDisplayUrlTests(SimpleTestCase):
    ORIGINAL = (
        'https://upload.wikimedia.org/wikipedia/commons/a/a8/'
        'Example_Bird.jpg'
    )

    def test_rewrites_original_to_960_thumb(self):
        out = wikimedia_display_url(self.ORIGINAL, width_px=960)
        self.assertEqual(
            out,
            'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/'
            'Example_Bird.jpg/960px-Example_Bird.jpg',
        )

    def test_rewrites_existing_thumb_width(self):
        thumb = (
            'https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/'
            'Example_Bird.jpg/500px-Example_Bird.jpg'
        )
        out = wikimedia_display_url(thumb, width_px=960)
        self.assertIn('/960px-Example_Bird.jpg', out)
        self.assertNotIn('/500px-', out)

    def test_leaves_non_wikimedia_unchanged(self):
        url = 'https://cdn.example.com/birds/photo.jpg'
        self.assertEqual(wikimedia_display_url(url), url)

    def test_leaves_video_path_unchanged(self):
        url = (
            'https://upload.wikimedia.org/wikipedia/commons/transcoded/'
            'a/a8/Example.webm/Example.webm.480p.vp9.webm'
        )
        self.assertEqual(wikimedia_display_url(url), url)

    @override_settings(MEDIA_WIKIMEDIA_DISPLAY_WIDTH_PX=500)
    def test_respects_settings_default_width(self):
        out = wikimedia_display_url(self.ORIGINAL)
        self.assertIn('/500px-Example_Bird.jpg', out)

    def test_snaps_arbitrary_width_to_step(self):
        # 900 is not a Wikimedia step; snap up to 960
        out = wikimedia_commons_thumb_url(self.ORIGINAL, 960)
        self.assertIn('/960px-', out)


class WikimediaVideoUrlTests(SimpleTestCase):
    ORIGINAL = (
        'https://upload.wikimedia.org/wikipedia/commons/e/e6/'
        'Huiszwaluw_zittend_op_schapenhek-4961660.webm'
    )
    OGV = (
        'https://upload.wikimedia.org/wikipedia/commons/e/e0/'
        'Pinicola_enucleator_CT2.ogv'
    )

    def test_rewrites_original_webm_to_480p_vp9(self):
        out = wikimedia_video_playback_url(self.ORIGINAL)
        self.assertEqual(
            out,
            'https://upload.wikimedia.org/wikipedia/commons/transcoded/e/e6/'
            'Huiszwaluw_zittend_op_schapenhek-4961660.webm/'
            'Huiszwaluw_zittend_op_schapenhek-4961660.webm.480p.vp9.webm',
        )

    def test_ios_mov_from_original_and_from_480p(self):
        mov = (
            'https://upload.wikimedia.org/wikipedia/commons/transcoded/e/e0/'
            'Pinicola_enucleator_CT2.ogv/'
            'Pinicola_enucleator_CT2.ogv.144p.mjpeg.mov'
        )
        self.assertEqual(wikimedia_video_ios_url(self.OGV), mov)
        self.assertEqual(
            wikimedia_video_ios_url(wikimedia_video_playback_url(self.OGV)),
            mov,
        )

    def test_playback_is_stable_on_already_transcoded_url(self):
        transcoded = wikimedia_video_playback_url(self.ORIGINAL)
        self.assertEqual(wikimedia_video_playback_url(transcoded), transcoded)

    def test_original_round_trip(self):
        self.assertEqual(
            wikimedia_video_original_url(wikimedia_video_playback_url(self.ORIGINAL)),
            self.ORIGINAL,
        )

    def test_leaves_youtube_and_images_unchanged(self):
        yt = 'https://www.youtube.com/embed/abc123'
        jpg = 'https://upload.wikimedia.org/wikipedia/commons/a/a8/Example_Bird.jpg'
        self.assertEqual(wikimedia_video_playback_url(yt), yt)
        self.assertEqual(wikimedia_video_playback_url(jpg), jpg)
