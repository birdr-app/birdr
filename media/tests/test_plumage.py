"""Sex and life-stage labels from iNaturalist and GBIF."""
from django.test import SimpleTestCase, TestCase

from jizz.models import Species
from media.models import Media, MediaPlumage
from media.plumage import (
    from_gbif_occurrence,
    from_inat_annotations,
    normalize_stage,
    save_source_plumage,
)


class ParseTests(SimpleTestCase):
    def test_inat_v2_ids(self):
        anns = [
            {'controlled_attribute_id': 1, 'controlled_value_id': 8, 'vote_score': 0},
            {'controlled_attribute_id': 9, 'controlled_value_id': 11, 'vote_score': 2},
            {'controlled_attribute_id': 17, 'controlled_value_id': 18},
        ]
        self.assertEqual(from_inat_annotations(anns), {'sex': 'male', 'stage': 'juvenile'})

    def test_inat_ignores_downvoted_and_non_bird_values(self):
        anns = [
            {'controlled_attribute_id': 1, 'controlled_value_id': 8, 'vote_score': -1},
            {'controlled_attribute_id': 9, 'controlled_value_id': 20},  # cannot be determined
            {'controlled_attribute_id': 1, 'controlled_value_id': 6},  # larva
        ]
        self.assertEqual(from_inat_annotations(anns), {'sex': '', 'stage': ''})

    def test_inat_v1_votes(self):
        down = [{'controlled_attribute_id': 9, 'controlled_value_id': 10,
                 'votes': [{'vote_flag': False}, {'vote_flag': True}, {'vote_flag': False}]}]
        up = [{'controlled_attribute_id': 9, 'controlled_value_id': 10, 'votes': [{'vote_flag': True}]}]
        self.assertEqual(from_inat_annotations(down)['sex'], '')
        self.assertEqual(from_inat_annotations(up)['sex'], 'female')

    def test_gbif(self):
        self.assertEqual(from_gbif_occurrence({'sex': 'FEMALE', 'lifeStage': 'Subadult'}),
                         {'sex': 'female', 'stage': 'immature'})
        self.assertEqual(from_gbif_occurrence({'sex': 'HERMAPHRODITE', 'lifeStage': 'Egg'}),
                         {'sex': '', 'stage': ''})

    def test_stage_synonyms(self):
        self.assertEqual(normalize_stage('Fledgling'), 'juvenile')
        self.assertEqual(normalize_stage('Nestling'), 'chick')


class SaveTests(TestCase):
    def setUp(self):
        species = Species.objects.create(name='Toro', name_latin='Phyllastrephus', code='PLM01')
        self.media = Media.objects.create(species=species, type='image', url='https://x/1.jpg', source='gbif')

    def test_empty_labels_store_nothing(self):
        self.assertFalse(save_source_plumage(self.media, 'gbif', {'sex': '', 'stage': ''}))
        self.assertFalse(MediaPlumage.objects.exists())

    def test_source_label_is_updated_but_human_label_is_kept(self):
        self.assertTrue(save_source_plumage(self.media, 'gbif', {'sex': 'male', 'stage': ''}))
        self.assertTrue(save_source_plumage(self.media, 'gbif', {'sex': 'male', 'stage': 'adult'}))
        self.assertEqual(MediaPlumage.objects.get().stage, 'adult')
        MediaPlumage.objects.update(source='human', stage='juvenile')
        self.assertFalse(save_source_plumage(self.media, 'gbif', {'sex': 'male', 'stage': 'adult'}))
        self.assertEqual(MediaPlumage.objects.get().stage, 'juvenile')
