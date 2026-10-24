from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from jizz.data_user_stats import media_reviews_per_user_rows
from jizz.models import Player, Species
from media.models import FlagMedia, Media, MediaReview
from media.non_photo import CLEAR, UNCLEAR, classify
from media.non_photo_sweep import AUTO_REVIEW_USERNAME
from media.scrapers.wikimedia import WikimediaScraper

WM = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/'


class ClassifyTests(SimpleTestCase):

    def assertKind(self, name, expected):
        result = classify(WM + name)
        self.assertEqual(result[0] if result else None, expected, f'{name} -> {result}')

    def test_not_bird_photos(self):
        for name in [
            'Sarothrura_lugens_dist.jpg',
            'Moho_braccatus_range.png',
            'Anthreptes_rectirostris_Keulemans.jpg',
            'Pterodroma_leucoptera_by_John_Gould.jpg',
            'A_history_of_the_birds_of_Europe_%28Pl._670%29.jpg',
            'A_monograph_of_the_pheasants_plate_XXXVI.jpg',
            'Xenops_-_1825-1834_-_Print_-_Iconographia_Zoologica.tif',
            'Study_skin_of_Passer_diffusus_6.jpg',
            'Hippolais_polyglotta_song_spectrogram.png',
            'Oenanthe_aquatica_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen-228.jpg',
            'File:Turdus_merula_eggs.jpg',
        ]:
            self.assertKind(name, CLEAR)

    def test_bird_photos_with_tricky_names(self):
        for name in [
            'Gould%27s_Petrel.jpg',
            'Audubon%27s_Oriole_Mission_TX_2018.jpg',
            'Sri_Lanka_Yellow_fronted_Barbet_at_Hanthana_mountain_range.jpg',
            'FMIB_50787_Auckland_Island_Shag_at_close_range.jpeg',
            'Kandy_dist_bird_photo.jpg',
            'Northern_Wheatear_(Oenanthe_oenanthe).jpg',
            'Orange-breasted_Sunbird.jpg',
        ]:
            self.assertKind(name, None)

    def test_needs_a_look(self):
        for name in ['Great_tit_at_nest.jpg', 'Some_bird_transparent_bg.png', 'Passeriformes_zookeys_722_Figure_7.jpg']:
            self.assertKind(name, UNCLEAR)

    def test_scraper_skips_clear_non_photos_only(self):
        self.assertTrue(WikimediaScraper._is_non_photo_file('File:Sarothrura_lugens_dist.jpg'))
        self.assertFalse(WikimediaScraper._is_non_photo_file('File:Great_tit_at_nest.jpg'))
        self.assertFalse(WikimediaScraper._is_non_photo_file('File:Gould%27s_Petrel.jpg'))


class SweepCommandTests(TestCase):

    def setUp(self):
        self.species = Species.objects.create(name='Bird', name_latin='Avis avis', code='npt01')
        self.photo = self.media('Avis_avis_in_flight.jpg')
        self.range_map = self.media('Avis_avis_dist.jpg')
        self.plate = self.media('Avis_avis_Keulemans.jpg')
        self.png = self.media('Avis_avis_transparent.png')
        self.approved_map = self.media('Avis_avis_range.png')
        person = Player.objects.create(name='Reviewer', language='en')
        MediaReview.objects.create(media=self.approved_map, player=person, review_type='approved')
        self.inat = Media.objects.create(species=self.species, type='image', source='inaturalist',
                                         url='https://inaturalist.org/photos/1/medium_dist.jpg')

    def media(self, name):
        return Media.objects.create(species=self.species, type='image', source='wikimedia', url=WM + name)

    def run_sweep(self, *args):
        out = StringIO()
        call_command('sweep_nonphoto_media', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_and_changes_nothing(self):
        out = self.run_sweep()
        self.assertIn('Not a bird photo (rejected with --apply): 2', out)
        self.assertIn('Needs a look (flagged with --apply): 1', out)
        self.assertIn('Skipped (approved by a person): 1', out)
        self.assertIn('Dry run', out)
        self.assertFalse(MediaReview.objects.filter(user__username=AUTO_REVIEW_USERNAME).exists())
        self.assertFalse(Media.objects.filter(hide=True).exists())

    def test_apply_hides_clear_cases_flags_unclear_and_is_idempotent(self):
        out = self.run_sweep('--apply')
        self.assertIn('Rejected and hidden: 2', out)
        self.assertIn('Flagged: 1', out)
        hidden = set(Media.objects.filter(hide=True).values_list('id', flat=True))
        self.assertEqual(hidden, {self.range_map.id, self.plate.id})
        review = MediaReview.objects.get(media=self.range_map)
        self.assertEqual(review.review_type, 'rejected')
        self.assertIn('range map', review.description)
        self.assertFalse(User.objects.get(username=AUTO_REVIEW_USERNAME).is_active)
        self.assertEqual(FlagMedia.objects.get().media, self.png)

        again = self.run_sweep('--apply')  # hidden ones are not scanned again; flags not duplicated
        self.assertIn('Rejected and hidden: 0', again)
        self.assertEqual(FlagMedia.objects.count(), 1)
        self.assertEqual(MediaReview.objects.filter(user__username=AUTO_REVIEW_USERNAME).count(), 2)

    def test_auto_reviewer_is_left_out_of_reviewer_stats(self):
        self.run_sweep('--apply')
        names = [row['name'] for row in media_reviews_per_user_rows()]
        self.assertEqual(names, ['Reviewer'])
