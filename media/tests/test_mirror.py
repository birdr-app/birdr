from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from jizz.models import Species
from media.display_urls import media_display_url, media_object_display_url
from media.mirror import commons_file_title, mirror_key, mirror_thumb_urls, mirrored_url
from media.models import Media, MediaReview

ORIGINAL = 'https://upload.wikimedia.org/wikipedia/commons/f/fb/Northern_Wheatear_%28Oenanthe%29.jpg'
THUMB_960 = (
    'https://upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Northern_Wheatear_%28Oenanthe%29.jpg/'
    '960px-Northern_Wheatear_%28Oenanthe%29.jpg'
)
BASE = 'https://birdr.de-fra-1.linodeobjects.com'
MIRRORED_960 = (
    f'{BASE}/upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Northern_Wheatear_%28Oenanthe%29.jpg/'
    '960px-Northern_Wheatear_%28Oenanthe%29.jpg'
)
S3 = dict(
    S3_HOST='de-fra-1.linodeobjects.com', S3_ACCESS_KEY='key', S3_SECRET_KEY='secret',
    MEDIA_MIRROR_BUCKET='birdr', MEDIA_MIRROR_BASE_URL=BASE,
)


class MirrorUrlTests(SimpleTestCase):
    def test_thumb_urls_for_both_sizes(self):
        thumbs = mirror_thumb_urls(ORIGINAL + '?utm_source=commons.wikimedia.org')
        self.assertEqual(len(thumbs), 2)
        self.assertIn('/500px-', thumbs[0])
        self.assertEqual(thumbs[1], THUMB_960)

    def test_no_thumbs_for_other_hosts_or_files(self):
        self.assertEqual(mirror_thumb_urls('https://static.inaturalist.org/photos/1/medium.jpg'), [])
        self.assertEqual(mirror_thumb_urls('https://upload.wikimedia.org/wikipedia/commons/a/ab/Song.ogg'), [])
        self.assertEqual(mirror_thumb_urls(None), [])

    def test_key_is_decoded_wikimedia_path(self):
        self.assertEqual(
            mirror_key(THUMB_960),
            'upload.wikimedia.org/wikipedia/commons/thumb/f/fb/Northern_Wheatear_(Oenanthe).jpg/'
            '960px-Northern_Wheatear_(Oenanthe).jpg',
        )

    @override_settings(MEDIA_MIRROR_BASE_URL=BASE + '/')
    def test_mirrored_url_keeps_wikimedia_path(self):
        url = mirrored_url(THUMB_960)
        self.assertEqual(url, MIRRORED_960)
        # Clients find the preview by swapping the step, as on Wikimedia.
        self.assertIn('wikimedia.org', url)
        self.assertIn('/960px-', url)

    @override_settings(MEDIA_MIRROR_BASE_URL=BASE)
    def test_mirrored_url_only_for_copied_sizes(self):
        self.assertIsNone(mirrored_url(THUMB_960.replace('960px-', '1280px-')))
        self.assertIsNone(mirrored_url(ORIGINAL))

    @override_settings(MEDIA_MIRROR_BASE_URL='')
    def test_mirrored_url_off_without_base(self):
        self.assertIsNone(mirrored_url(THUMB_960))

    def test_commons_file_title(self):
        self.assertEqual(commons_file_title(ORIGINAL), 'File:Northern Wheatear (Oenanthe).jpg')
        self.assertEqual(commons_file_title(THUMB_960), 'File:Northern Wheatear (Oenanthe).jpg')


@override_settings(MEDIA_MIRROR_BASE_URL=BASE, MEDIA_WIKIMEDIA_DISPLAY_WIDTH_PX=960)
class MirrorDisplayUrlTests(SimpleTestCase):
    def test_mirrored_media_served_from_bucket(self):
        self.assertEqual(media_display_url(ORIGINAL, mirrored=True), MIRRORED_960)

    def test_unmirrored_media_served_from_wikimedia(self):
        self.assertEqual(media_display_url(ORIGINAL), THUMB_960)

    def test_media_object(self):
        media = Media(url=ORIGINAL, mirrored_at=None)
        self.assertEqual(media_object_display_url(media), THUMB_960)
        media.mirrored_at = '2026-10-24T10:00:00Z'
        self.assertEqual(media_object_display_url(media), MIRRORED_960)

    def test_non_wikimedia_unchanged(self):
        url = 'https://static.inaturalist.org/photos/1/medium.jpg'
        self.assertEqual(media_display_url(url, mirrored=True), url)


def _response(status=200, content=b'jpeg', content_type='image/jpeg', headers=None):
    response = mock.Mock(status_code=status, content=content)
    response.headers = {'Content-Type': content_type, **(headers or {})}
    response.raise_for_status = mock.Mock(
        side_effect=None if status < 400 else Exception(f'HTTP {status}')
    )
    return response


@override_settings(**S3)
class MirrorCommandTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='Northern Wheatear', name_latin='Oenanthe oenanthe', code='norwhe')
        self.media = Media.objects.create(species=self.species, type='image', source='wikimedia', url=ORIGINAL)
        self.client_mock = mock.Mock()
        patches = [
            mock.patch('media.management.commands.mirror_wikimedia_media.bucket_client', return_value=self.client_mock),
            mock.patch('media.management.commands.mirror_wikimedia_media.time.sleep'),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_command(self, *args, get=None, head_status=200):
        with mock.patch('requests.Session.get', side_effect=get or (lambda *a, **k: _response())), \
                mock.patch('requests.head', return_value=mock.Mock(status_code=head_status)):
            out = StringIO()
            call_command('mirror_wikimedia_media', *args, stdout=out, stderr=StringIO())
            return out.getvalue()

    def test_copies_both_sizes(self):
        self.run_command()
        keys = [c.kwargs['Key'] for c in self.client_mock.put_object.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertTrue(keys[0].endswith('/500px-Northern_Wheatear_(Oenanthe).jpg'))
        self.assertEqual(self.client_mock.put_object.call_args.kwargs['ContentType'], 'image/jpeg')
        self.media.refresh_from_db()
        self.assertIsNotNone(self.media.mirrored_at)

    def test_skips_already_mirrored(self):
        self.run_command()
        self.client_mock.reset_mock()
        self.run_command()
        self.client_mock.put_object.assert_not_called()

    def test_retries_after_429(self):
        responses = iter([_response(429, headers={'Retry-After': '2'}), _response(), _response()])
        self.run_command(get=lambda *a, **k: next(responses))
        self.media.refresh_from_db()
        self.assertIsNotNone(self.media.mirrored_at)

    def test_failed_download_not_marked(self):
        self.run_command(get=lambda *a, **k: _response(404))
        self.media.refresh_from_db()
        self.assertIsNone(self.media.mirrored_at)

    def test_stops_when_objects_not_public(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.run_command(head_status=403)
        self.media.refresh_from_db()
        self.assertIsNone(self.media.mirrored_at)

    @mock.patch('media.non_photo_sweep.auto_reviewer')
    def test_check_deleted_removes_copy_and_rejects(self, auto_reviewer):
        from django.contrib.auth import get_user_model

        auto_reviewer.return_value = (get_user_model().objects.create(username='bot'), None)
        self.run_command()
        api = _response(content_type='application/json')
        api.json = lambda: {'query': {'pages': [
            {'title': 'File:Northern Wheatear (Oenanthe).jpg', 'missing': True},
        ]}}
        self.run_command('--check-deleted', get=lambda *a, **k: api)
        self.assertEqual(self.client_mock.delete_object.call_count, 2)
        self.media.refresh_from_db()
        self.assertIsNone(self.media.mirrored_at)
        self.assertTrue(self.media.hide)
        self.assertTrue(MediaReview.objects.filter(media=self.media, review_type=MediaReview.REJECTED).exists())
