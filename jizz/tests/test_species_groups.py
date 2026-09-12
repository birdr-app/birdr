from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from jizz.game_question_selection import _query_option_species_ids
from jizz.models import Country, CountrySpecies, Game
from jizz.services.species_groups import (
    apply_missing_translations,
    assign_species_group_ids,
    group_name_for_locale,
    match_group,
    overlay_bundled_names,
    rows_from_sppgroups,
    sppgroup_intervals,
    unique_slug,
)
from jizz.tests.taxonomy_helpers import make_species_group, make_species_with_taxonomy
from media.models import Media


class SpeciesGroupUtilTests(SimpleTestCase):
    def test_unique_slug_avoids_collisions(self):
        used = set()
        self.assertEqual(unique_slug('Shorebirds', used), 'shorebirds')
        self.assertEqual(unique_slug('Shorebirds', used), 'shorebirds-2')

    def test_taxon_order_by_species_code(self):
        from jizz.services.species_groups import taxon_order_by_species_code

        lookup = taxon_order_by_species_code(
            [
                {'category': 'species', 'speciesCode': 'mallar', 'taxonOrder': 400.0},
                {'category': 'spuh', 'speciesCode': 'waterfowl', 'taxonOrder': 1.0},
                {'category': 'species', 'speciesCode': '', 'taxonOrder': 2.0},
            ]
        )
        self.assertEqual(lookup, {'mallar': 400.0})

    def test_rows_from_sppgroups_uses_dutch_names_by_group_order(self):
        en_groups = [
            {
                'groupName': 'Shorebirds',
                'groupOrder': 30,
                'taxonOrderBounds': [[5725.0, 6356.0]],
            },
            {
                'groupName': 'Wood-Warblers',
                'groupOrder': 213,
                'taxonOrderBounds': [[33946.0, 34398.0]],
            },
        ]
        nl_groups = [
            {'groupName': 'Steltlopers', 'groupOrder': 30},
            {'groupName': 'Amerikaanse zangers', 'groupOrder': 213},
        ]
        rows = rows_from_sppgroups(en_groups, nl_groups)
        by_slug = {row['slug']: row for row in rows}
        self.assertEqual(by_slug['shorebirds']['name_nl'], 'Steltlopers')
        self.assertEqual(by_slug['wood-warblers']['ebird_name'], 'Wood-Warblers')
        self.assertEqual(by_slug['wood-warblers']['name_nl'], 'Amerikaanse zangers')

    def test_rows_from_sppgroups_fills_all_app_language_fields(self):
        en_groups = [
            {
                'groupName': 'Shorebirds',
                'groupOrder': 30,
                'taxonOrderBounds': [[5725.0, 6356.0]],
            },
        ]
        rows = rows_from_sppgroups(
            en_groups,
            locale_groups={
                'nl': [{'groupName': 'Steltlopers', 'groupOrder': 30}],
                'es': [{'groupName': 'Aves limícolas', 'groupOrder': 30}],
                'fr': [{'groupName': 'Limicoles', 'groupOrder': 30}],
                'de': [{'groupName': 'Watvögel', 'groupOrder': 30}],
                'pt_br': [{'groupName': 'Maçaricos e afins', 'groupOrder': 30}],
            },
        )
        row = rows[0]
        self.assertEqual(row['name_es'], 'Aves limícolas')
        self.assertEqual(row['name_fr'], 'Limicoles')
        self.assertEqual(row['name_de'], 'Watvögel')
        self.assertEqual(row['name_pt_br'], 'Maçaricos e afins')
        self.assertEqual(row['name_it'], 'Shorebirds')
        self.assertEqual(row['name_ja'], 'Shorebirds')

    def test_apply_missing_translations_skips_locales_ebird_already_filled(self):
        rows = [
            {
                'name_en': 'Shorebirds',
                'name_es': 'Aves limícolas',
                'name_it': 'Shorebirds',
                'name_ja': 'Shorebirds',
                'name_nl': 'Steltlopers',
                'name_fr': 'Limicoles',
                'name_de': 'Watvögel',
                'name_pt_br': 'Maçaricos',
            },
            {
                'name_en': 'Waterfowl',
                'name_es': 'Anátidas',
                'name_it': 'Waterfowl',
                'name_ja': 'Waterfowl',
                'name_nl': 'Watervogels',
                'name_fr': 'Anatidés',
                'name_de': 'Wasservögel',
                'name_pt_br': 'Anatídeos',
            },
        ]

        def fake_translate(names, language):
            suffix = 'it' if language == 'it' else 'ja'
            self.assertTrue(all(name in ('Shorebirds', 'Waterfowl') for name in names))
            return {name: f'{name}-{suffix}' for name in names}

        filled = apply_missing_translations(rows, translate_names=fake_translate)
        self.assertEqual(filled, ['it', 'ja'])
        self.assertEqual(rows[0]['name_es'], 'Aves limícolas')
        self.assertEqual(rows[0]['name_it'], 'Shorebirds-it')
        self.assertEqual(rows[0]['name_ja'], 'Shorebirds-ja')

    def test_group_name_for_locale_falls_back_to_english(self):
        row = {
            'name_en': 'Shorebirds',
            'name_nl': 'Steltlopers',
            'name_es': 'Aves limícolas',
            'name_pt_br': 'Maçaricos',
        }
        self.assertEqual(group_name_for_locale(row, 'es'), 'Aves limícolas')
        self.assertEqual(group_name_for_locale(row, 'pt-BR'), 'Maçaricos')
        self.assertEqual(group_name_for_locale(row, 'ja'), 'Shorebirds')
        self.assertEqual(group_name_for_locale(row, 'zz'), 'Shorebirds')

    def test_overlay_bundled_names_fills_english_fallbacks(self):
        rows = [
            {
                'ebird_name': 'Shorebirds',
                'slug': 'shorebirds',
                'name_en': 'Shorebirds',
                'name_es': 'Aves limícolas',
                'name_it': 'Shorebirds',
                'name_ja': 'Shorebirds',
            }
        ]
        overlay_bundled_names(
            rows,
            catalog={
                'Shorebirds': {
                    'name_es': 'should not replace',
                    'name_it': 'Limicoli',
                    'name_ja': 'シギ・チドリ類',
                }
            },
        )
        self.assertEqual(rows[0]['name_es'], 'Aves limícolas')
        self.assertEqual(rows[0]['name_it'], 'Limicoli')
        self.assertEqual(rows[0]['name_ja'], 'シギ・チドリ類')

    def test_match_group_picks_narrowest_interval(self):
        intervals = sppgroup_intervals(
            [
                {'groupName': 'Waterfowl', 'taxonOrderBounds': [[200.0, 500.0]]},
                {'groupName': 'Screamers', 'taxonOrderBounds': [[232.0, 250.0]]},
            ]
        )
        self.assertEqual(match_group(240.0, intervals), 'Screamers')
        self.assertEqual(match_group(300.0, intervals), 'Waterfowl')
        self.assertIsNone(match_group(10.0, intervals))
        self.assertIsNone(match_group(None, intervals))


class SpeciesGroupAssignTests(TestCase):
    def test_assign_species_group_ids_by_tax_ordering(self):
        shorebirds = make_species_group('shorebirds', name_en='Shorebirds', sort_order=30)
        waterfowl = make_species_group('waterfowl', name_en='Waterfowl', sort_order=7)
        intervals = [
            (5725.0, 6356.0, 631.0, shorebirds.id),
            (236.0, 793.0, 557.0, waterfowl.id),
        ]
        by_group = assign_species_group_ids(
            taxon_orders=[
                (1, 6000.0),
                (2, 400.0),
                (3, None),
                (4, 10.0),
            ],
            intervals=intervals,
        )
        self.assertEqual(by_group[shorebirds.id], [1])
        self.assertEqual(by_group[waterfowl.id], [2])
        self.assertEqual(set(by_group[None]), {3, 4})


class SpeciesGroupApiAndFilterTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]
        self.shorebirds = make_species_group(
            'shorebirds', name_en='Shorebirds', name_nl='Steltlopers', sort_order=30
        )
        self.shorebirds.name_es = 'Aves limícolas'
        self.shorebirds.name_pt_br = 'Maçaricos e afins'
        self.shorebirds.save(update_fields=['name_es', 'name_pt_br'])
        self.waterfowl = make_species_group(
            'waterfowl', name_en='Waterfowl', name_nl='Watervogels', sort_order=7
        )
        self.wader = make_species_with_taxonomy(
            name='Oystercatcher',
            name_latin='Haematopus ostralegus',
            code='eureoy1',
            species_group=self.shorebirds,
            tax_ordering=6000.0,
        )
        self.extra_waders = [
            make_species_with_taxonomy(
                name=f'Wader {i}',
                name_latin=f'Calidris wader{i}',
                code=f'wader{i}',
                species_group=self.shorebirds,
                tax_ordering=6001.0 + i,
            )
            for i in range(3)
        ]
        self.duck = make_species_with_taxonomy(
            name='Mallard',
            name_latin='Anas platyrhynchos',
            code='mallar1',
            species_group=self.waterfowl,
            tax_ordering=400.0,
        )
        for species in (self.wader, self.duck, *self.extra_waders):
            CountrySpecies.objects.create(
                country=self.country, species=species, status='native'
            )
            Media.objects.create(
                species=species,
                type='image',
                url=f'https://example.com/{species.code}.jpg',
                source='test',
            )

    def test_groups_list_omits_groups_with_fewer_than_four_species(self):
        client = APIClient()
        response = client.get('/api/groups/', {'country': 'NL'})
        self.assertEqual(response.status_code, 200)
        slugs = {row['species_group']: row for row in response.data}
        self.assertEqual(slugs['shorebirds']['name_nl'], 'Steltlopers')
        self.assertEqual(slugs['shorebirds']['name_es'], 'Aves limícolas')
        self.assertEqual(slugs['shorebirds']['name_pt_br'], 'Maçaricos e afins')
        self.assertEqual(slugs['shorebirds']['count'], 4)
        self.assertNotIn('waterfowl', slugs)

    def test_game_species_group_limits_candidates(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            rarity=Game.RARIT_REGULAR,
            species_group='shorebirds',
        )
        ids = _query_option_species_ids(game)
        self.assertEqual(set(ids), {self.wader.id, *(s.id for s in self.extra_waders)})

    def test_game_create_accepts_species_group(self):
        from jizz.models import Player

        player = Player.objects.create(name='Host', language='en')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {player.token}')
        response = client.post(
            '/api/games/',
            {
                'country': 'NL',
                'level': 'beginner',
                'length': 5,
                'media': 'images',
                'rarity': 'regular',
                'species_group': 'shorebirds',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['species_group'], 'shorebirds')
        game = Game.objects.get(token=response.data['token'])
        self.assertEqual(game.species_group, 'shorebirds')


class SpeciesGroupDataViewsTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]
        group = make_species_group(
            'shorebirds', name_en='Shorebirds', name_nl='Steltlopers', sort_order=30
        )
        species = make_species_with_taxonomy(
            name='Oystercatcher',
            name_latin='Haematopus ostralegus',
            code='eureoy2',
            species_group=group,
        )
        CountrySpecies.objects.create(country=self.country, species=species, status='native')

    def test_data_groups_page(self):
        res = Client().get(reverse('data-taxon-groups'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Shorebirds')
        self.assertContains(res, 'Steltlopers')

    def test_data_index_links_groups(self):
        res = Client().get(reverse('data-index'))
        self.assertContains(res, reverse('data-taxon-groups'))
