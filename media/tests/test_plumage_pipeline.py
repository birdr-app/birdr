"""Plumage pipeline: Commons parser, write rules, scope, backfill and AI labelling (stubbed)."""
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from jizz.models import Species
from media import plumage_ai
from media.models import Media, MediaPlumage, MediaReview
from media.plumage import (
    apply_ai_label,
    effective_confidence,
    from_commons_extmetadata,
    from_commons_text,
    normalize_season,
    save_source_plumage,
    set_human_plumage,
)


class CommonsParserTests(SimpleTestCase):
    def test_sex_stage_season_from_description(self):
        self.assertEqual(
            from_commons_text('File:Mallard.jpg', '<p>Female Mallard in eclipse plumage</p>'),
            {'sex': 'female', 'stage': '', 'season': 'eclipse'},
        )
        self.assertEqual(
            from_commons_text('Adult male Tufted Duck in breeding plumage'),
            {'sex': 'male', 'stage': 'adult', 'season': 'breeding'},
        )

    def test_female_is_not_read_as_male(self):
        self.assertEqual(from_commons_text('A female blackbird')['sex'], 'female')
        self.assertEqual(from_commons_text('♂ Eurasian Teal')['sex'], 'male')

    def test_non_breeding_is_not_breeding(self):
        self.assertEqual(from_commons_text('Dunlin in non-breeding plumage')['season'], 'non_breeding')
        self.assertEqual(from_commons_text('Dunlin, winter plumage')['season'], 'non_breeding')
        self.assertEqual(from_commons_text('Black-headed Gull summer plumage')['season'], 'breeding')
        self.assertEqual(from_commons_text('Non-breeding and breeding plumage side by side')['season'], '')

    def test_stage_synonyms(self):
        self.assertEqual(from_commons_text('Juvenile Robin')['stage'], 'juvenile')
        self.assertEqual(from_commons_text('First-winter Herring Gull')['stage'], 'immature')
        self.assertEqual(from_commons_text('Subadult Gannet')['stage'], 'immature')
        self.assertEqual(from_commons_text('Coot chicks')['stage'], 'chick')
        self.assertEqual(from_commons_text('Volwassen vrouwtje merel'), {'sex': 'female', 'stage': 'adult', 'season': ''})

    def test_conflicting_values_say_nothing(self):
        self.assertEqual(from_commons_text('Male and female Mallard')['sex'], '')
        self.assertEqual(from_commons_text('Adult feeding a juvenile')['stage'], '')

    def test_nothing_to_find(self):
        self.assertEqual(from_commons_text('Mallard in flight', 'Anas platyrhynchos'), {'sex': '', 'stage': '', 'season': ''})
        self.assertEqual(from_commons_text(None, ''), {'sex': '', 'stage': '', 'season': ''})

    def test_extmetadata_uses_description_and_categories(self):
        meta = {
            'ObjectName': {'value': 'Anas platyrhynchos 01'},
            'ImageDescription': {'value': '<a href="x">Duck</a> on a pond'},
            'Categories': {'value': 'Anas platyrhynchos|Female Anas platyrhynchos|Anas platyrhynchos in eclipse plumage'},
        }
        self.assertEqual(from_commons_extmetadata(meta), {'sex': 'female', 'stage': '', 'season': 'eclipse'})
        self.assertEqual(from_commons_extmetadata(None), {'sex': '', 'stage': '', 'season': ''})

    def test_season_values(self):
        self.assertEqual(normalize_season('Non-breeding'), 'non_breeding')
        self.assertEqual(normalize_season('summer'), 'breeding')
        self.assertEqual(normalize_season('spring'), '')


class PlumageTestBase(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='Mallard', name_latin='Anas platyrhynchos', code='mallar')
        self.media = self.photo()

    def photo(self, **kwargs):
        defaults = dict(species=self.species, type='image', source='gbif', url='https://x/1.jpg')
        defaults.update(kwargs)
        return Media.objects.create(**defaults)


class WriteRulesTests(PlumageTestBase):
    def test_source_fills_season_and_keeps_other_fields(self):
        self.assertTrue(save_source_plumage(self.media, 'gbif', {'sex': 'female', 'stage': ''}))
        self.assertTrue(save_source_plumage(self.media, 'wikimedia', {'sex': '', 'stage': '', 'season': 'eclipse'}))
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.season, row.source), ('female', 'eclipse', 'wikimedia'))
        self.assertFalse(save_source_plumage(self.media, 'wikimedia', {'season': 'eclipse'}))

    def test_dry_run_writes_nothing(self):
        self.assertTrue(save_source_plumage(self.media, 'gbif', {'sex': 'male'}, dry_run=True))
        self.assertFalse(MediaPlumage.objects.exists())

    def test_source_overrides_ai_values_but_keeps_the_ai_row(self):
        MediaPlumage.objects.create(media=self.media, source='ai', sex='male', stage='adult', confidence=0.7, model_version='m')
        self.assertTrue(save_source_plumage(self.media, 'gbif', {'sex': 'female'}))
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.source, row.confidence), ('female', 'adult', 'ai', 0.7))

    def test_human_row_is_never_changed(self):
        set_human_plumage(self.media, sex='male')
        self.assertFalse(save_source_plumage(self.media, 'gbif', {'sex': 'female', 'season': 'breeding'}))
        self.assertEqual(apply_ai_label(self.media, {'sex': 'female', 'stage': 'adult', 'season': '', 'confidence': 1}, 'm'), 'human')
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.source, row.confidence), ('male', '', 'human', 1.0))

    def test_ai_creates_a_row(self):
        label = {'sex': 'female', 'stage': 'adult', 'season': '', 'confidence': 0.85}
        self.assertEqual(apply_ai_label(self.media, label, 'haiku:v1', 0.6), 'created')
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.season, row.source, row.confidence, row.model_version),
                         ('female', 'adult', '', 'ai', 0.85, 'haiku:v1'))

    def test_ai_only_fills_empty_fields_of_a_source_row(self):
        MediaPlumage.objects.create(media=self.media, source='inaturalist', sex='male')
        label = {'sex': 'female', 'stage': 'juvenile', 'season': '', 'confidence': 0.9}
        self.assertEqual(apply_ai_label(self.media, label, 'm'), 'filled')
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.source, row.confidence), ('male', 'juvenile', 'ai', 0.9))

    def test_ai_replaces_its_own_earlier_label(self):
        apply_ai_label(self.media, {'sex': 'male', 'stage': 'adult', 'season': '', 'confidence': 0.7}, 'm1')
        apply_ai_label(self.media, {'sex': 'female', 'stage': '', 'season': '', 'confidence': 0.9}, 'm2')
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.confidence, row.model_version), ('female', 'adult', 0.9, 'm2'))

    def test_low_confidence_records_the_attempt_only(self):
        label = {'sex': 'female', 'stage': 'adult', 'season': '', 'confidence': 0.3}
        self.assertEqual(apply_ai_label(self.media, label, 'm', 0.6), 'low_confidence')
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.stage, row.model_version, row.confidence), ('', '', 'm', 0.3))

    def test_effective_confidence(self):
        self.assertEqual(effective_confidence(MediaPlumage(source='human', confidence=None)), 1.0)
        self.assertEqual(effective_confidence(MediaPlumage(source='ai', confidence=0.5)), 0.5)
        self.assertEqual(effective_confidence(MediaPlumage(source='gbif')), 0.9)


class AiHelpersTests(SimpleTestCase):
    def test_parse_label(self):
        self.assertEqual(
            plumage_ai.parse_label('{"sex":"female","stage":"unknown","season":"eclipse","confidence":0.82}'),
            {'sex': 'female', 'stage': '', 'season': 'eclipse', 'confidence': 0.82},
        )
        self.assertEqual(plumage_ai.parse_label('{"sex":"x","stage":"adult","season":"","confidence":7}')['sex'], '')
        self.assertEqual(plumage_ai.parse_label('{"sex":"x","stage":"adult","season":"","confidence":7}')['confidence'], 1.0)
        self.assertIsNone(plumage_ai.parse_label('not json'))
        self.assertIsNone(plumage_ai.parse_label('{"sex":"male"}'))

    def test_label_from_message(self):
        text = SimpleNamespace(type='text', text='{"sex":"male","stage":"adult","season":"breeding","confidence":0.9}')
        thinking = SimpleNamespace(type='thinking', thinking='')
        ok = SimpleNamespace(stop_reason='end_turn', content=[thinking, text])
        self.assertEqual(plumage_ai.label_from_message(ok)['sex'], 'male')
        self.assertIsNone(plumage_ai.label_from_message(SimpleNamespace(stop_reason='refusal', content=[text])))
        self.assertIsNone(plumage_ai.label_from_message(SimpleNamespace(stop_reason='max_tokens', content=[thinking])))

    def test_request_shape(self):
        item = {'url': 'https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg',
                'species': 'Mallard', 'latin': 'Anas platyrhynchos'}
        params = plumage_ai.build_request(item)
        self.assertEqual(params['model'], 'claude-haiku-5-5')
        image = params['messages'][0]['content'][0]
        self.assertEqual(image['source']['url'], 'https://inaturalist-open-data.s3.amazonaws.com/photos/1/medium.jpg')
        self.assertEqual(params['output_config']['format']['schema'], plumage_ai.LABEL_SCHEMA)
        self.assertIn('Anas platyrhynchos', params['messages'][0]['content'][1]['text'])
        self.assertNotIn('temperature', params)


class ScopeAndCommandTests(PlumageTestBase):
    def setUp(self):
        super().setUp()
        self.other = Species.objects.create(name='Teal', name_latin='Anas crecca', code='eurtea')
        self.teal = self.photo(species=self.other, url='https://x/2.jpg')
        self.hidden = self.photo(url='https://x/3.jpg', hide=True)

    def run_label(self, *args, labels=None, **kwargs):
        out = StringIO()
        sent = {}

        def fake(items, **kw):
            sent['items'] = items
            return {i['media_id']: (labels or {}).get(i['media_id'], {'sex': 'female', 'stage': 'adult', 'season': '', 'confidence': 0.9})
                    for i in items}

        with patch('media.management.commands.label_media_plumage.classify_images', side_effect=fake):
            call_command('label_media_plumage', *args, stdout=out, **kwargs)
        return out.getvalue(), sent.get('items')

    def test_scope_is_required(self):
        with self.assertRaises(CommandError):
            call_command('label_media_plumage', stdout=StringIO())

    def test_species_scope_sends_visible_photos_only(self):
        out, items = self.run_label('--species', 'mallar')
        self.assertEqual([i['media_id'] for i in items], [self.media.id])
        self.assertEqual(items[0]['latin'], 'Anas platyrhynchos')
        self.assertEqual(MediaPlumage.objects.get().source, 'ai')

    def test_media_ids_scope_and_dry_run(self):
        out, items = self.run_label('--media-ids', f'{self.teal.id},{self.hidden.id}', '--dry-run')
        self.assertIsNone(items)  # nothing sent
        self.assertIn('2 photos need an AI label', out)
        self.assertFalse(MediaPlumage.objects.exists())

    def test_human_complete_and_already_asked_photos_are_skipped(self):
        set_human_plumage(self.media, sex='male')
        MediaPlumage.objects.create(media=self.teal, source='ai', sex='male', model_version='old')
        MediaPlumage.objects.create(media=self.hidden, source='gbif', sex='male', stage='adult', season='breeding')
        out, items = self.run_label('--species', 'mallar', '--species', 'eurtea', '--media-ids', str(self.hidden.id))
        self.assertIsNone(items)
        self.assertIn('0 photos need', out)

    def test_redo_asks_ai_rows_again_but_not_human(self):
        set_human_plumage(self.media, sex='male')
        MediaPlumage.objects.create(media=self.teal, source='ai', sex='male', model_version='old', confidence=0.7)
        out, items = self.run_label('--species', 'mallar,eurtea', '--redo')
        self.assertEqual([i['media_id'] for i in items], [self.teal.id])
        self.assertEqual(MediaPlumage.objects.get(media=self.teal).sex, 'female')
        self.assertEqual(MediaPlumage.objects.get(media=self.media).source, 'human')

    def test_limit_and_min_confidence(self):
        out, items = self.run_label('--species', 'mallar,eurtea', '--limit', '1', '--min-confidence', '0.95')
        self.assertEqual(len(items), 1)
        row = MediaPlumage.objects.get()
        self.assertEqual((row.sex, row.source), ('', 'ai'))  # asked, but too unsure to write
        self.assertIn('low_confidence=1', out)

    def review(self, media, review_type, username='reviewer'):
        from django.contrib.auth import get_user_model

        user, _ = get_user_model().objects.get_or_create(username=username)
        return MediaReview.objects.create(media=media, review_type=review_type, user=user)

    def test_approved_narrows_the_scope_to_latest_approvals(self):
        self.review(self.media, 'approved')
        self.review(self.teal, 'approved')
        self.review(self.teal, 'rejected', username='second')  # the latest review counts
        out, items = self.run_label('--species', 'mallar,eurtea', '--approved')
        self.assertEqual([i['media_id'] for i in items], [self.media.id])

    def test_approved_alone_covers_every_species_but_no_hidden_photos(self):
        for m in (self.media, self.teal, self.hidden):
            self.review(m, 'approved')
        Media.objects.filter(id=self.hidden.id).update(hide=True)  # an approval unhides, so hide afterwards
        out, items = self.run_label('--approved')
        ids = {i['media_id'] for i in items}  # a kept test database may hold other approved photos
        self.assertLessEqual({self.media.id, self.teal.id}, ids)
        self.assertNotIn(self.hidden.id, ids)

    def test_failed_photo_gets_no_row(self):
        out, _ = self.run_label('--species', 'mallar', labels={self.media.id: None})
        self.assertFalse(MediaPlumage.objects.exists())
        self.assertIn('failed=1', out)

    def test_course_scope(self):
        from jizz.courses.content import COURSES

        slug = next(iter(COURSES))
        with patch('media.plumage_scope.course_scope', return_value=({self.teal.id}, {self.species.id})):
            out, items = self.run_label('--course', slug)
        self.assertEqual({i['media_id'] for i in items}, {self.media.id, self.teal.id})  # hidden mallard photo stays out

    def test_course_scope_reads_lesson_files_and_picks(self):
        from jizz.courses.content import COURSES
        from media.plumage_scope import course_scope

        lessons = [{'week': 1, 'birds': [{'species_id': 7, 'media': {'card': [1, 2], 'quiz': [3]}}]}]
        picked = [{'week': 1, 'birds': [{'species_id': 7, 'media': {'card': [9], 'quiz': [4]}}]}]
        slug = next(iter(COURSES))
        with patch('jizz.courses.content.course_lessons', return_value=lessons), \
                patch('jizz.courses.content.effective_lessons', return_value=picked):
            self.assertEqual(course_scope(slug), ({1, 2, 3, 4, 9}, {7}))
        with self.assertRaises(CommandError):
            course_scope('no-such-course')


class BackfillCommandTests(PlumageTestBase):
    def setUp(self):
        super().setUp()
        self.inat = self.photo(source='inaturalist', link='https://www.inaturalist.org/observations/111', url='https://x/i.jpg')
        self.commons = self.photo(
            source='wikimedia', link='https://commons.wikimedia.org/wiki/File:Mallard_f.jpg',
            url='https://upload.wikimedia.org/wikipedia/commons/a/ab/Mallard_f.jpg',
        )

    def run_backfill(self, *args):
        from media.management.commands import backfill_media_plumage as cmd

        calls = []

        def fake_get(url, params, retries=3):
            calls.append((url, params))
            if 'inaturalist' in url:
                return {'results': [{'id': 111, 'annotations': [
                    {'controlled_attribute_id': 9, 'controlled_value_id': 10, 'vote_score': 1},
                ]}]}
            if 'wikimedia' in url:
                return {'query': {
                    'normalized': [],
                    'pages': {'1': {'title': 'File:Mallard f.jpg', 'imageinfo': [{'extmetadata': {
                        'ImageDescription': {'value': 'Female in eclipse plumage'}}}]}},
                }}
            return {'results': []}

        out = StringIO()
        with patch.object(cmd, '_get', side_effect=fake_get), patch.object(cmd.time, 'sleep'):
            call_command('backfill_media_plumage', *args, stdout=out, stderr=StringIO())
        return out.getvalue(), calls

    def test_scoped_run_looks_up_inat_and_commons(self):
        out, calls = self.run_backfill('--species', 'mallar', '--source', 'inaturalist', '--source', 'wikimedia')
        self.assertEqual(MediaPlumage.objects.get(media=self.inat).sex, 'female')
        commons = MediaPlumage.objects.get(media=self.commons)
        self.assertEqual((commons.sex, commons.season, commons.source), ('female', 'eclipse', 'wikimedia'))
        self.assertEqual(calls[-1][1]['titles'], 'File:Mallard f.jpg')

    def test_dry_run_writes_nothing(self):
        out, _ = self.run_backfill('--species', 'mallar', '--dry-run', '--source', 'inaturalist')
        self.assertFalse(MediaPlumage.objects.exists())
        self.assertIn('would be labelled', out)

    def test_scoped_run_rechecks_labelled_photos_but_not_human_ones(self):
        MediaPlumage.objects.create(media=self.inat, source='inaturalist', stage='adult')
        self.run_backfill('--media-ids', str(self.inat.id), '--source', 'inaturalist')
        self.assertEqual(MediaPlumage.objects.get().sex, 'female')
        set_human_plumage(self.inat, sex='male')
        out, calls = self.run_backfill('--media-ids', str(self.inat.id), '--source', 'inaturalist')
        self.assertEqual(MediaPlumage.objects.get().sex, 'male')
        self.assertEqual(calls, [])  # nothing left to look up

    def test_unscoped_run_skips_labelled_media(self):
        MediaPlumage.objects.create(media=self.inat, source='inaturalist', stage='adult')
        out, calls = self.run_backfill('--source', 'inaturalist')
        self.assertEqual(calls, [])
