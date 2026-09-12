from django.test import SimpleTestCase, override_settings

from media.display_urls import inaturalist_display_url, media_display_url


class INaturalistDisplayUrlTests(SimpleTestCase):
    ORIGINAL = 'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/original.jpg'
    LARGE = 'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/large.jpg'
    MEDIUM = 'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/medium.jpg'
    STATIC = 'https://static.inaturalist.org/photos/470442148/original.jpeg'

    def test_rewrites_original_to_medium(self):
        self.assertEqual(inaturalist_display_url(self.ORIGINAL), self.MEDIUM)

    def test_rewrites_large_to_medium(self):
        self.assertEqual(inaturalist_display_url(self.LARGE), self.MEDIUM)

    def test_does_not_upscale_medium(self):
        self.assertEqual(inaturalist_display_url(self.MEDIUM), self.MEDIUM)

    def test_static_host_and_jpeg_extension(self):
        self.assertEqual(
            inaturalist_display_url(self.STATIC),
            'https://static.inaturalist.org/photos/470442148/medium.jpeg',
        )

    def test_preserves_query_string(self):
        url = self.ORIGINAL + '?v=2'
        self.assertEqual(inaturalist_display_url(url), self.MEDIUM + '?v=2')

    @override_settings(MEDIA_INATURALIST_DISPLAY_SIZE='large')
    def test_respects_settings_size(self):
        self.assertEqual(inaturalist_display_url(self.ORIGINAL), self.LARGE)
        self.assertEqual(inaturalist_display_url(self.LARGE), self.LARGE)

    def test_leaves_non_inat_unchanged(self):
        url = 'https://cdn.example.com/photos/1/original.jpg'
        self.assertEqual(inaturalist_display_url(url), url)


class MediaDisplayUrlTests(SimpleTestCase):
    def test_wikimedia_and_inat(self):
        wiki = 'https://upload.wikimedia.org/wikipedia/commons/c/ca/Bar-tailed_Godwit.jpg'
        out = media_display_url(wiki)
        self.assertIn('/960px-Bar-tailed_Godwit.jpg', out)

        inat = 'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/original.jpg'
        self.assertEqual(
            media_display_url(inat),
            'https://inaturalist-open-data.s3.amazonaws.com/photos/604502879/medium.jpg',
        )

    def test_wikimedia_video_becomes_480p(self):
        webm = (
            'https://upload.wikimedia.org/wikipedia/commons/e/e6/'
            'Huiszwaluw_zittend_op_schapenhek-4961660.webm'
        )
        out = media_display_url(webm)
        self.assertIn('.480p.vp9.webm', out)
        self.assertIn('/transcoded/', out)
