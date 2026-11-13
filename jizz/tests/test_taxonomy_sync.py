from django.test import TestCase

from jizz.models import (
    Country, CountrySpecies, Species, SpeciesAlias, Subspecies, TaxonomyChange, resolve_species_by_code,
)
from jizz.services.taxonomy_sync import apply_lump, apply_proposed, detect_changes, record_changes
from media.models import Media


def sp(code, name='X', sci='G s'):
    return {'category': 'species', 'speciesCode': code, 'comName': name, 'sciName': sci}


def sub(code, report_as, cat='issf'):
    return {'category': cat, 'speciesCode': code, 'reportAs': report_as, 'comName': code, 'sciName': 'G s f'}


class DetectTests(TestCase):
    def setUp(self):
        self.redpoll = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1')
        self.lesser = Species.objects.create(name='Lesser Redpoll', name_latin='Acanthis cabaret', code='lesred1')
        self.gone = Species.objects.create(name='Gone', name_latin='Gone gone', code='gone1')

    def kinds(self, rows):
        return {(c['change_type'], tuple(c['old_codes']), tuple(c['new_codes'])) for c in detect_changes(rows)}

    def test_lump_retired_new_rename(self):
        rows = [
            sp('redpol1', sci='Acanthis flammea'), sub('lesred1', 'redpol1'),
            sp('brandnew'),
        ]
        k = self.kinds(rows)
        self.assertIn(('lump', ('lesred1',), ('redpol1',)), k)
        self.assertIn(('retired', ('gone1',), ()), k)
        self.assertIn(('new', (), ('brandnew',)), k)
        rows[0]['sciName'] = 'Acanthis new'
        self.assertIn(('rename', ('redpol1',), ('redpol1',)), self.kinds(rows))

    def test_split_when_subspecies_becomes_species(self):
        Subspecies.objects.create(species=self.redpoll, code='mealy', name='Mealy')
        rows = [sp('redpol1', sci='Acanthis flammea'), sp('lesred1', sci='Acanthis cabaret'),
                sp('gone1', sci='Gone gone'), sp('mealy')]
        self.assertIn(('split', ('redpol1',), ('mealy', 'redpol1')), self.kinds(rows))

    def test_empty_feed_refused(self):
        with self.assertRaises(ValueError):
            detect_changes([])

    def test_record_is_idempotent(self):
        changes = detect_changes([sp('redpol1', sci='Acanthis flammea'), sub('lesred1', 'redpol1'), sp('gone1', sci='Gone gone')])
        self.assertEqual(record_changes(changes, None)['recorded'], 1)
        self.assertEqual(record_changes(changes, None)['recorded'], 0)


class ApplyLumpTests(TestCase):
    def test_lump_moves_media_country_and_retires(self):
        survivor = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1')
        old = Species.objects.create(name='Lesser Redpoll', name_latin='Acanthis cabaret', code='lesred1')
        nl, be = Country.objects.get_or_create(code='NL')[0], Country.objects.get_or_create(code='BE')[0]
        CountrySpecies.objects.create(country=nl, species=survivor)
        CountrySpecies.objects.create(country=nl, species=old)
        CountrySpecies.objects.create(country=be, species=old)
        m = Media.objects.create(species=old, type='image', url='http://x/1.jpg')
        Subspecies.objects.create(species=survivor, code='lesred1', name='Lesser Redpoll', name_latin='Acanthis flammea cabaret', source=Subspecies.SOURCE_EBIRD)
        change = TaxonomyChange.objects.create(change_type='lump', old_codes=['lesred1'], new_codes=['redpol1'])

        stats = apply_proposed('2025')

        self.assertEqual(stats['lumps'], 1)
        m.refresh_from_db(); old.refresh_from_db(); change.refresh_from_db()
        self.assertEqual(m.species, survivor)
        self.assertEqual(m.subspecies.code, 'lesred1')
        self.assertEqual(old.merged_into, survivor)
        self.assertIsNotNone(old.retired_at)
        self.assertEqual(old.ebird_category, 'issf')
        self.assertEqual(old.name_latin, 'Acanthis flammea cabaret')
        self.assertEqual(change.report['applied']['former_species']['name_latin'], 'Acanthis cabaret')
        self.assertEqual(Subspecies.objects.get(code='lesred1').source, Subspecies.SOURCE_LUMP)
        self.assertEqual(Subspecies.objects.get(code='lesred1').name_latin, 'Acanthis flammea cabaret')
        self.assertEqual(resolve_species_by_code('lesred1'), old)  # still a current Species row
        self.assertTrue(SpeciesAlias.objects.filter(code='lesred1', species=survivor).exists())
        self.assertFalse(CountrySpecies.objects.filter(species=old).exists())
        self.assertEqual(CountrySpecies.objects.filter(species=survivor).count(), 2)
        self.assertEqual(change.status, 'applied')
        self.assertEqual(change.report['applied']['country_dropped'], 1)
        self.assertEqual(change.report['applied']['country_dropped_snapshot'][0]['country_id'], nl.pk)
        self.assertEqual(change.report['applied']['former_species']['name'], 'Lesser Redpoll')


class LumpCommonnessTests(TestCase):
    def test_lump_merges_country_commonness_into_survivor(self):
        survivor = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1')
        old = Species.objects.create(name='Common Redpoll', name_latin='Acanthis flammea', code='comred')
        nl = Country.objects.get_or_create(code='NL')[0]
        CountrySpecies.objects.create(country=nl, species=survivor, status='rare', frequency='vagrant')
        CountrySpecies.objects.create(country=nl, species=old, status='native', frequency='common', frequency_pct=30.0)
        TaxonomyChange.objects.create(change_type='lump', old_codes=['comred'], new_codes=['redpol1'])

        apply_proposed('2026')

        row = CountrySpecies.objects.get(country=nl, species=survivor)
        self.assertEqual((row.status, row.frequency, row.frequency_pct), ('native', 'common', 30.0))


class LumpGamesAndApiTests(TestCase):
    def setUp(self):
        from jizz.models import Game
        self.Game = Game
        self.survivor = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1', slug='redpoll')
        self.old = Species.objects.create(name='Lesser Redpoll', name_latin='Acanthis cabaret', code='lesred1', slug='lesser-redpoll')
        self.other = Species.objects.create(name='Siskin', name_latin='Spinus spinus', code='eursis')

    def lump(self):
        TaxonomyChange.objects.create(change_type='lump', old_codes=['lesred1'], new_codes=['redpol1'])
        return apply_proposed('2026')

    def test_games_repointed_and_collapsed_pair_cleared(self):
        focus = self.Game.objects.create(focus_species=self.old)
        pair = self.Game.objects.create(pair_species_low=self.survivor, pair_species_high=self.old)
        pair2 = self.Game.objects.create(pair_species_low=self.old, pair_species_high=self.other)
        mix = self.Game.objects.create()
        mix.mixup_species.set([self.old, self.survivor, self.other])
        self.assertEqual(self.lump()['lumps'], 1)
        for g in (focus, pair, pair2, mix):
            g.refresh_from_db()
        self.assertEqual(focus.focus_species, self.survivor)
        self.assertIsNone(pair.pair_species_low_id)
        self.assertIsNone(pair.pair_species_high_id)
        self.assertEqual((pair2.pair_species_low, pair2.pair_species_high), (self.survivor, self.other))
        self.assertEqual(set(mix.mixup_species.all()), {self.survivor, self.other})

    def test_api_resolves_retired_species_to_survivor_and_hides_it_from_list(self):
        self.lump()
        r = self.client.get(f'/api/species/{self.old.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['id'], self.survivor.id)


class SupersedeTests(TestCase):
    def test_proposal_no_longer_detected_is_ignored(self):
        TaxonomyChange.objects.create(change_type='retired', old_codes=['x1'], new_codes=[])
        stats = record_changes([], None)
        self.assertEqual(stats['superseded'], 1)
        self.assertEqual(TaxonomyChange.objects.get().status, 'ignored')


class LumpedFormAdminTests(TestCase):
    def test_retired_species_page_links_to_its_tagged_media(self):
        from django.contrib.auth.models import User
        from jizz.services.taxonomy_sync import apply_proposed
        survivor = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1', slug='r')
        old = Species.objects.create(name='Arctic Redpoll', name_latin='Acanthis hornemanni', code='hoared', slug='a')
        Media.objects.create(species=old, type='image', url='http://x/1.jpg')
        TaxonomyChange.objects.create(change_type='lump', old_codes=['hoared'], new_codes=['redpol1'])
        apply_proposed()
        admin_user = User.objects.create_superuser('adm', 'a@example.com', 'pw')
        self.client.force_login(admin_user)
        page = self.client.get(f'/admin/jizz/species/{old.pk}/change/')
        self.assertContains(page, 'Media of this form is stored on')
        self.assertContains(page, '1 images')
        form = Subspecies.objects.get(code='hoared')
        self.assertEqual(self.client.get(f'/admin/media/media/?subspecies__id__exact={form.pk}').status_code, 200)


class RefreshSpeciesNamesTests(TestCase):
    def test_names_of_split_and_lumped_species_are_refreshed_per_language(self):
        from jizz.models import Language, SpeciesName, TaxonomyChange
        from jizz.services.taxonomy_sync import refresh_species_names

        nl = Language.objects.create(code='nl', name='Dutch')
        keep = Species.objects.create(name='Saltmarsh Willet', name_latin='Tringa semipalmata', code='willet2')
        kid = Species.objects.create(name='Prairie Willet', name_latin='Tringa inornata', code='willet3')
        lump = Species.objects.create(name='Survivor', name_latin='Genus survivor', code='survvr')
        other = Species.objects.create(name='Other', name_latin='Genus other', code='other1')
        SpeciesName.objects.create(species=keep, language=nl, name='Willet')
        TaxonomyChange.objects.create(change_type='split', old_codes=['willet2'], new_codes=['willet2', 'willet3'],
                                      status='applied', report={'targets': {'willet2': keep.id, 'willet3': kid.id}})
        TaxonomyChange.objects.create(change_type='lump', old_codes=['x'], new_codes=['survvr'], status='applied',
                                      report={'into_species_id': lump.id})
        feed = {'nl': [
            {'speciesCode': 'willet2', 'comName': 'Zoutmoeras-Willet'}, {'speciesCode': 'willet3', 'comName': 'Prairie-Willet'},
            {'speciesCode': 'survvr', 'comName': 'Overlever'}, {'speciesCode': 'other1', 'comName': 'Ander'},
        ]}
        stats = refresh_species_names(fetch=lambda locale, categories: feed[locale])
        self.assertEqual((stats['created'], stats['updated']), (2, 1))
        self.assertEqual(SpeciesName.objects.get(species=keep, language=nl).name, 'Zoutmoeras-Willet')
        self.assertEqual(SpeciesName.objects.get(species=kid, language=nl).name, 'Prairie-Willet')
        self.assertFalse(SpeciesName.objects.filter(species=other).exists())
