"""Copies of the same file for one species: dedupe, flagging, and next-media."""
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.models import Country, CountrySpecies, Game, Player, PlayerScore, Species
from jizz.question_play import _eligible_media_list, fetch_eligible_media_for_species
from media.duplicates import apply, image_url_exists, scan
from media.models import Media, MediaReview

PHOTO = 'https://inaturalist-open-data.s3.amazonaws.com/photos/215347550/original.jpg'


class DuplicateMediaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.species = Species.objects.create(name='Toro', name_latin='Phyllastrephus', code='DUP01')
        self.player = Player.objects.create(name='P', language='en')
        self.gbif = Media.objects.create(species=self.species, type='image', url=PHOTO, source='gbif')
        self.inat = Media.objects.create(species=self.species, type='image', url=PHOTO, source='inaturalist')

    def _review(self, media, review_type):
        return MediaReview.objects.create(media=media, player=self.player, review_type=review_type)

    def test_scan_and_apply_hide_the_later_copy(self):
        report = scan()
        self.assertEqual(report.groups, 1)
        self.assertEqual(report.assignments, {self.inat.id: self.gbif.id})

        self.assertEqual(apply(report), 1)
        self.inat.refresh_from_db()
        self.gbif.refresh_from_db()
        self.assertTrue(self.inat.hide)
        self.assertEqual(self.inat.duplicate_of_id, self.gbif.id)
        self.assertFalse(self.gbif.hide)
        self.assertEqual(scan().groups, 0)

    def test_scan_keeps_the_approved_copy(self):
        self._review(self.inat, MediaReview.APPROVED)
        report = scan()
        self.assertEqual(report.assignments, {self.gbif.id: self.inat.id})

    def test_scan_hides_visible_copy_of_a_rejected_file(self):
        # Rejected before twin propagation existed: the other copy is still visible.
        MediaReview.objects.bulk_create([
            MediaReview(media=self.gbif, player=self.player, review_type=MediaReview.REJECTED),
        ])
        Media.objects.filter(pk=self.gbif.pk).update(hide=True)

        report = scan()
        self.assertEqual(report.assignments, {self.inat.id: self.gbif.id})
        self.assertEqual(report.hidden_under_rejected, 1)

    def test_scan_ignores_other_species_and_types(self):
        other = Species.objects.create(name='Other', name_latin='Other', code='DUP02')
        Media.objects.create(species=other, type='image', url='https://example.com/x.jpg', source='gbif')
        Media.objects.create(species=self.species, type='video', url='https://example.com/x.jpg', source='gbif')
        Media.objects.create(species=self.species, type='image', url='https://example.com/x.jpg', source='gbif')
        self.assertEqual(scan().groups, 1)

    def test_command_dry_run_changes_nothing(self):
        out = StringIO()
        call_command('dedupe_media', stdout=out)
        self.assertIn('Rows to hide: 1', out.getvalue())
        self.inat.refresh_from_db()
        self.assertFalse(self.inat.hide)

    def test_command_apply(self):
        call_command('dedupe_media', '--apply', stdout=StringIO())
        self.inat.refresh_from_db()
        self.assertEqual(self.inat.duplicate_of_id, self.gbif.id)

    def test_rejecting_one_copy_hides_the_other(self):
        self._review(self.gbif, MediaReview.REJECTED)
        self.inat.refresh_from_db()
        self.assertTrue(self.inat.hide)
        self.assertEqual(self.inat.duplicate_of_id, self.gbif.id)
        self.assertEqual(fetch_eligible_media_for_species(self.species.id, 'image'), [])

    def test_approving_a_duplicate_keeps_it_hidden(self):
        apply(scan())
        self._review(self.inat, MediaReview.APPROVED)
        self.inat.refresh_from_db()
        self.assertTrue(self.inat.hide)

    def test_eligible_list_shows_each_file_once(self):
        rows = list(Media.objects.filter(species=self.species).prefetch_related('reviews'))
        self.assertEqual([m.id for m in _eligible_media_list(rows)], [self.gbif.id])

    def test_image_url_exists_matches_any_source(self):
        self.assertTrue(image_url_exists(self.species, PHOTO))
        self.assertFalse(image_url_exists(self.species, 'https://example.com/new.jpg'))
        self.assertFalse(image_url_exists(self.species, None))


class NextMediaWithDuplicatesTests(TestCase):
    """POST /api/questions/<id>/next-media/ after flagging a photo that was stored twice."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        country = Country.objects.get_or_create(code='UG', defaults={'name': 'Uganda'})[0]
        self.species = Species.objects.create(name='Toro', name_latin='Phyllastrephus', code='DUP03')
        CountrySpecies.objects.create(country=country, species=self.species, status='native')
        self.first = Media.objects.create(species=self.species, type='image', url=PHOTO, source='gbif')
        self.copy = Media.objects.create(species=self.species, type='image', url=PHOTO, source='inaturalist')
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=country, level='beginner', length=5, media='images', host=self.player,
        )
        self.question = self.game.add_question()
        PlayerScore.objects.get_or_create(player=self.player, game=self.game)

    def _flag_and_advance(self, media):
        MediaReview.objects.create(media=media, player=self.player, review_type=MediaReview.REJECTED)
        return self.client.post(
            f'/api/questions/{self.question.id}/next-media/',
            {'player_token': self.player.token, 'excluded_media_id': media.id},
            format='json',
        )

    def test_flagged_photo_does_not_come_back_as_its_copy(self):
        response = self._flag_and_advance(self.first)
        self.assertEqual(response.status_code, 409)

    def test_next_media_returns_a_different_photo(self):
        other = Media.objects.create(
            species=self.species, type='image', url='https://example.com/other.jpg', source='wikimedia',
        )
        response = self._flag_and_advance(self.first)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['images'][0]['id'], other.id)
