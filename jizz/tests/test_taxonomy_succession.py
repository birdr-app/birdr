from unittest import mock

from django.test import TestCase

from jizz.models import (
    Country, CountrySpecies, Game, Species, SpeciesAlias, Subspecies, TaxonomyChange, resolve_species_by_code,
)
from jizz.services.taxonomy_succession import (
    apply_succession, classify_held_media, collect_media, match_taxon, reconcile_countries,
    rescore_commonness,
)
from jizz.services.taxonomy_sync import apply_proposed, detect_changes
from media.models import Media


def sp_row(code, name, sci, order=1.0):
    return {'category': 'species', 'speciesCode': code, 'comName': name, 'sciName': sci,
            'taxonOrder': order, 'familySciName': 'Troglodytidae'}


def sub_row(code, report_as, sci='X y z'):
    return {'category': 'issf', 'speciesCode': code, 'reportAs': report_as, 'comName': code, 'sciName': sci}


class DetectSuccessionTests(TestCase):
    def setUp(self):
        self.wren = Species.objects.create(name='Marsh Wren', name_latin='Cistothorus palustris', code='marwre')

    def feed(self):
        return [
            sp_row('eamwre1', 'Eastern Marsh Wren', 'Cistothorus palustris'),
            sp_row('wesmwr1', 'Western Marsh Wren', 'Cistothorus paludicola'),
            sub_row('marwre3', 'eamwre1', 'Cistothorus palustris palustris'),
            sub_row('marwre5', 'wesmwr1', 'Cistothorus paludicola paludicola'),
        ]

    def test_split_found_through_previously_linked_subspecies(self):
        for code in ("marwre3", "marwre5"):
            Subspecies.objects.create(species=self.wren, code=code, name=code)
        ch = [c for c in detect_changes(self.feed()) if c['change_type'] == 'split']
        self.assertEqual(len(ch), 1)
        rep = ch[0]['report']
        self.assertEqual(sorted(ch[0]['new_codes']), ['eamwre1', 'wesmwr1'])
        self.assertEqual(rep['continuing'], 'eamwre1')
        self.assertEqual(rep['subspecies_map'], {'marwre3': 'eamwre1', 'marwre5': 'wesmwr1'})
        # the children are not also reported as plain new species
        self.assertEqual([c for c in detect_changes(self.feed()) if c['change_type'] == 'new'], [])

    def test_same_name_successor_already_in_table_is_a_recode(self):
        Species.objects.create(name='Dusky Myzomela', name_latin='Myzomela obscura', code='dusmyz5', slug='x')
        old = Species.objects.create(name='Dusky Myzomela', name_latin='Myzomela obscura', code='dusmyz1', slug='y')
        ch = [c for c in detect_changes([sp_row('dusmyz5', 'Dusky Myzomela', 'Myzomela obscura')])
              if c['old_codes'] == ['dusmyz1']]
        self.assertEqual(ch[0]['change_type'], 'rename')
        self.assertEqual(ch[0]['report']['kind'], 'recode')
        self.assertEqual(ch[0]['report']['species_id'], old.id)


class DetectLineageTests(TestCase):
    """Splits the current feed no longer links, found through the previous release."""

    def prev_willet(self):
        return [
            sp_row('willet1', 'Saltmarsh/Prairie Willet', 'Tringa semipalmata'),
            {**sub_row('willet2', 'willet1', 'Tringa semipalmata semipalmata'), 'category': 'issf'},
            {**sub_row('willet3', 'willet1', 'Tringa semipalmata inornata'), 'category': 'issf'},
        ]

    def now_willet(self):
        return [sp_row('willet2', 'Saltmarsh Willet', 'Tringa semipalmata'),
                sp_row('willet3', 'Prairie Willet', 'Tringa inornata')]

    def test_child_of_a_recoded_species_is_a_split_not_a_new_species(self):
        sp = Species.objects.create(name='Saltmarsh Willet', name_latin='Tringa semipalmata', code='willet2')
        SpeciesAlias.objects.create(code='willet1', species=sp, reason='rename')
        ch = detect_changes(self.now_willet(), self.prev_willet())
        self.assertEqual([c['change_type'] for c in ch], ['split'])
        self.assertEqual(ch[0]['old_codes'], ['willet2'])
        self.assertEqual(ch[0]['new_codes'], ['willet2', 'willet3'])
        self.assertEqual(ch[0]['report']['continuing'], 'willet2')
        self.assertEqual(ch[0]['report']['species_id'], sp.id)

    def test_without_previous_release_the_child_stays_new(self):
        Species.objects.create(name='Saltmarsh Willet', name_latin='Tringa semipalmata', code='willet2')
        ch = detect_changes(self.now_willet())
        self.assertEqual([c['change_type'] for c in ch], ['new'])

    def test_parent_gone_from_feed_splits_into_both(self):
        sp = Species.objects.create(name='Willet', name_latin='Tringa semipalmata', code='willet1')
        ch = detect_changes(self.now_willet(), self.prev_willet())
        self.assertEqual([c['change_type'] for c in ch], ['split'])
        self.assertEqual(ch[0]['old_codes'], ['willet1'])
        self.assertEqual(ch[0]['new_codes'], ['willet2', 'willet3'])
        self.assertEqual(ch[0]['report']['species_id'], sp.id)

    def test_child_with_two_possible_parents_is_left_alone(self):
        Species.objects.create(name='A', name_latin='Tringa a', code='willet2')
        Species.objects.create(name='B', name_latin='Tringa b', code='willet1')
        prev = [sub_row('willet3', 'willet1'), sub_row('willet2', 'willet1')]
        ch = detect_changes([sp_row('willet2', 'A', 'Tringa a'), sp_row('willet3', 'Prairie Willet', 'Tringa inornata')], prev)
        self.assertEqual([c['change_type'] for c in ch if c['change_type'] != 'retired'], ['new'])

    def test_manual_parent_names_a_split_the_feed_does_not_show(self):
        sp = Species.objects.create(name='Mexican Motmot', name_latin='Momotus mexicanus', code='rucmot1')
        feed = [sp_row('rucmot1', 'Mexican Motmot', 'Momotus mexicanus'),
                sp_row('rucmot6', 'Guatemalan Motmot', 'Momotus castaneiceps')]
        self.assertEqual([c['change_type'] for c in detect_changes(feed)], ['new'])
        ch = detect_changes(feed, manual_parents={'rucmot6': 'rucmot1'})
        self.assertEqual([c['change_type'] for c in ch], ['split'])
        self.assertEqual(ch[0]['new_codes'], ['rucmot1', 'rucmot6'])
        self.assertEqual(ch[0]['report']['species_id'], sp.id)

    def test_trinomial_of_the_child_resolves_through_its_own_epithet(self):
        parent = Species.objects.create(name='Saltmarsh Willet', name_latin='Tringa semipalmata', code='willet2')
        child = Species.objects.create(name='Prairie Willet', name_latin='Tringa inornata', code='willet3')
        change = TaxonomyChange.objects.create(
            change_type='split', old_codes=['willet2'], new_codes=['willet2', 'willet3'],
            report={'targets': {'willet2': parent.id, 'willet3': child.id}, 'name_latin': 'Tringa semipalmata'},
        )
        from jizz.services.taxonomy_succession import _target_table
        self.assertEqual(match_taxon('Tringa semipalmata inornata', _target_table(change), 'Tringa semipalmata'), 'willet3')


class ApplySuccessionTests(TestCase):
    def setUp(self):
        self.old = Species.objects.create(name='Marsh Wren', name_latin='Cistothorus palustris', code='marwre', slug='marsh-wren')
        self.nl = Country.objects.get_or_create(code='NL')[0]
        self.us = Country.objects.get_or_create(code='US')[0]
        CountrySpecies.objects.create(country=self.nl, species=self.old)
        CountrySpecies.objects.create(country=self.us, species=self.old, status='native')
        for i in range(3):
            Media.objects.create(species=self.old, type='image', url=f'http://x/{i}.jpg', source='inaturalist',
                                 link=f'https://www.inaturalist.org/observations/{i}')
        self.hidden = Media.objects.create(species=self.old, type='image', url='http://x/h.jpg', hide=True)
        self.change = TaxonomyChange.objects.create(
            change_type='split', old_codes=['marwre'], new_codes=['eamwre1', 'wesmwr1'],
            report={
                'species_id': self.old.id, 'name': 'Marsh Wren', 'name_latin': 'Cistothorus palustris',
                'continuing': 'eamwre1', 'subspecies_map': {},
                'children': {
                    'eamwre1': {'code': 'eamwre1', 'name': 'Eastern Marsh Wren', 'name_latin': 'Cistothorus palustris',
                                'tax_ordering': 1.0, 'family_sci': 'Troglodytidae', 'exists_id': None},
                    'wesmwr1': {'code': 'wesmwr1', 'name': 'Western Marsh Wren', 'name_latin': 'Cistothorus paludicola',
                                'tax_ordering': 2.0, 'family_sci': 'Troglodytidae', 'exists_id': None},
                },
            },
        )

    def test_split_recodes_in_place_creates_child_and_holds_unclear_media(self):
        game = Game.objects.create(focus_species=self.old)
        apply_succession(self.change, version='2026')
        self.old.refresh_from_db()
        self.assertEqual((self.old.code, self.old.name), ('eamwre1', 'Eastern Marsh Wren'))
        self.assertIsNone(self.old.retired_at)
        west = Species.objects.get(code='wesmwr1')
        self.assertEqual(west.name_latin, 'Cistothorus paludicola')
        self.assertEqual(resolve_species_by_code('marwre'), self.old)
        self.assertEqual(Media.objects.filter(held_for_change=self.change, hide=True).count(), 3)
        self.hidden.refresh_from_db()
        self.assertIsNone(self.hidden.held_for_change)  # already hidden before: not ours to release
        game.refresh_from_db()
        self.assertEqual(game.focus_species, self.old)

    def test_classify_releases_to_the_right_species_and_unknown_stays_held(self):
        apply_succession(self.change)
        names = {0: 'Cistothorus paludicola', 1: 'Cistothorus palustris', 2: None}

        def namer(m):
            return names[int(m.link.rsplit('/', 1)[1])]

        stats = classify_held_media(self.change, namer=namer)
        west = Species.objects.get(code='wesmwr1')
        self.assertEqual(stats['released'], 1)  # only the unambiguous new name; the old binomial fits both
        self.assertEqual(west.media.filter(hide=False).count(), 1)
        self.assertEqual(Media.objects.filter(held_for_change=self.change).count(), 2)
        # attempted ones are not asked again
        self.assertEqual(classify_held_media(self.change, namer=namer)['checked'], 0)

    def test_countries_follow_ebird_lists_and_collect_media_runs_for_short_species(self):
        apply_succession(self.change)
        west = Species.objects.get(code='wesmwr1')
        lists = {'NL': [], 'US': ['wesmwr1', 'eamwre1']}
        stats = reconcile_countries(self.change, fetch=lambda c: lists.get(c))
        self.assertEqual(stats['added'], 1)
        self.assertEqual(stats['removed'], 1)
        self.assertTrue(CountrySpecies.objects.filter(country=self.us, species=west).exists())
        self.assertFalse(CountrySpecies.objects.filter(country=self.nl, species=self.old).exists())
        scraped = []
        out = collect_media(self.change, scrape=scraped.append)
        self.assertEqual(sorted(scraped), sorted([self.old.id, west.id]))
        self.assertEqual(out['scraped'], 2)
        self.assertEqual(collect_media(self.change, scrape=scraped.append)['scraped'], 0)

    def test_commonness_is_rescored_from_st_data_and_missing_data_is_retried(self):
        apply_succession(self.change)
        west = Species.objects.get(code='wesmwr1')
        CountrySpecies.objects.create(country=self.us, species=west, status='native', frequency='common', frequency_pct=40.0)
        frames = {'eamwre1': object(), 'wesmwr1': None}  # no distribution data for the new split yet
        with mock.patch('jizz.ebird_st_commonness.countries_in_regional_stats', return_value=['US']), \
                mock.patch('jizz.ebird_st_commonness.parse_species_commonness',
                           return_value={'abundance_mean_max': 1.0, 'frequency_pct': 2.5}), \
                mock.patch('jizz.ebird_st_commonness.classify_from_abundance', return_value=('rare', None)):
            stats = rescore_commonness(self.change, access_key='k', load=lambda code: frames.get(code))
        self.assertEqual(stats, {'rescored': 1, 'no_data': 1, 'rows': 1})
        row = CountrySpecies.objects.get(country=self.us, species=self.old)
        self.assertEqual((row.frequency, row.frequency_pct), ('rare', 2.5))
        self.assertEqual(CountrySpecies.objects.get(country=self.us, species=west).frequency, 'common')  # kept
        frames['wesmwr1'] = object()
        with mock.patch('jizz.ebird_st_commonness.countries_in_regional_stats', return_value=['US']), \
                mock.patch('jizz.ebird_st_commonness.parse_species_commonness',
                           return_value={'abundance_mean_max': 1.0, 'frequency_pct': 9.0}), \
                mock.patch('jizz.ebird_st_commonness.classify_from_abundance', return_value=('uncommon', None)):
            again = rescore_commonness(self.change, access_key='k', load=lambda code: frames.get(code))
        self.assertEqual(again['rescored'], 1)  # only the one that had no data before
        self.assertEqual(CountrySpecies.objects.get(country=self.us, species=west).frequency, 'uncommon')

    def test_unverified_countries_stay_pending(self):
        apply_succession(self.change)
        stats = reconcile_countries(self.change, fetch=lambda c: None)
        self.assertEqual(stats['unverified'], 2)
        self.change.refresh_from_db()
        self.assertEqual(sorted(self.change.report['countries_pending']), ['NL', 'US'])


class RecodeMergeTests(TestCase):
    def test_duplicate_successor_merges_media_without_losing_rows(self):
        new = Species.objects.create(name='Dusky Myzomela', name_latin='Myzomela obscura', code='dusmyz5', slug='a')
        old = Species.objects.create(name='Dusky Myzomela', name_latin='Myzomela obscura', code='dusmyz1', slug='b')
        shared = Media.objects.create(species=new, type='image', url='http://x/same.jpg')
        mine_dup = Media.objects.create(species=old, type='image', url='http://x/same.jpg')
        only_old = Media.objects.create(species=old, type='image', url='http://x/old.jpg')
        change = TaxonomyChange.objects.create(
            change_type='rename', old_codes=['dusmyz1'], new_codes=['dusmyz5'],
            report={'kind': 'recode', 'species_id': old.id, 'continuing': 'dusmyz5', 'subspecies_map': {},
                    'children': {'dusmyz5': {'code': 'dusmyz5', 'name': 'Dusky Myzomela', 'name_latin': 'Myzomela obscura',
                                             'exists_id': new.id}}},
        )
        self.assertEqual(apply_proposed()['recodes'], 1)
        for m in (shared, mine_dup, only_old, old):
            m.refresh_from_db()
        self.assertEqual(mine_dup.species, new)
        self.assertEqual(mine_dup.duplicate_of, shared)
        self.assertTrue(mine_dup.hide)
        self.assertEqual(only_old.species, new)
        self.assertFalse(only_old.hide)
        self.assertIsNotNone(old.retired_at)
        self.assertEqual(old.merged_into, new)
        self.assertEqual(resolve_species_by_code('dusmyz1'), old)
        self.assertTrue(SpeciesAlias.objects.filter(code='dusmyz1', species=new).exists())
        self.assertEqual(Media.objects.filter(held_for_change__isnull=False).count(), 0)


class MatchTaxonTests(TestCase):
    def test_rules(self):
        t = [{'code': 'e', 'latin': 'Cistothorus palustris', 'epithets': {'griseus'}},
             {'code': 'w', 'latin': 'Cistothorus paludicola', 'epithets': {'plesius'}}]
        old = 'Cistothorus palustris'
        self.assertEqual(match_taxon('Cistothorus palustris griseus', t, old), 'e')
        self.assertEqual(match_taxon('Cistothorus palustris plesius', t, old), 'w')
        self.assertEqual(match_taxon('Cistothorus paludicola', t, old), 'w')
        self.assertIsNone(match_taxon('Cistothorus palustris', t, old))  # old name fits both
        self.assertIsNone(match_taxon(None, t, old))


class CarveOutTests(TestCase):
    def test_species_stays_and_subspecies_becomes_its_own_species(self):
        stay = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='redpol1', slug='r')
        Subspecies.objects.create(species=stay, code='mealy', name='Mealy', source=Subspecies.SOURCE_EBIRD)
        tagged = Subspecies.objects.get(code='mealy')
        m_tagged = Media.objects.create(species=stay, type='image', url='http://x/t.jpg', subspecies=tagged)
        m_plain = Media.objects.create(species=stay, type='image', url='http://x/p.jpg')
        feed = [sp_row('redpol1', 'Redpoll', 'Acanthis flammea'), sp_row('mealy', 'Mealy Redpoll', 'Acanthis islandica')]
        change = [c for c in detect_changes(feed) if c['change_type'] == 'split'][0]
        tc = TaxonomyChange.objects.create(**change)
        self.assertEqual(apply_proposed()['splits'], 1)
        new = Species.objects.get(code='mealy')
        m_tagged.refresh_from_db(); m_plain.refresh_from_db(); stay.refresh_from_db()
        self.assertEqual(m_tagged.species, new)
        self.assertFalse(m_tagged.hide)
        self.assertEqual(m_plain.species, stay)
        self.assertTrue(m_plain.hide)          # untagged: held until classified
        self.assertEqual(m_plain.held_for_change, tc)
        self.assertIsNone(stay.retired_at)
        self.assertEqual(stay.code, 'redpol1')
        self.assertFalse(Subspecies.objects.filter(code='mealy').exists())


class RegionClassifyTests(ApplySuccessionTests):
    def test_media_is_sorted_by_where_it_was_taken_when_only_one_species_lives_there(self):
        apply_succession(self.change)
        west = Species.objects.get(code='wesmwr1')
        ca = Country.objects.get_or_create(code='US-CA', defaults={'name': 'California', 'parent_id': 'US'})[0]
        fl = Country.objects.get_or_create(code='US-FL', defaults={'name': 'Florida', 'parent_id': 'US'})[0]
        for c in (ca, fl):
            Country.objects.filter(pk=c.pk).update(parent_id='US')
        CountrySpecies.objects.create(country=ca, species=west)
        CountrySpecies.objects.create(country=fl, species=self.old)
        CountrySpecies.objects.create(country=self.us, species=west)  # both occur in the US as a whole
        where = {0: {'state': 'California', 'country_code': 'US'}, 1: {'state': 'Florida', 'country_code': 'US'},
                 2: {'country_code': 'US'}}
        stats = classify_held_media(
            self.change, infoer=lambda m: {'name': 'Cistothorus palustris', **where[int(m.link.rsplit('/', 1)[1])]})
        self.assertEqual(stats['released'], 2)
        self.assertEqual(west.media.filter(hide=False).count(), 1)        # California -> Western
        self.assertEqual(self.old.media.filter(hide=False).count(), 1)    # Florida -> Eastern
        self.assertEqual(Media.objects.filter(held_for_change=self.change).count(), 1)  # US only: both occur


class RepairCountriesTests(TestCase):
    def test_regions_an_earlier_recode_removed_are_rechecked_after_a_split(self):
        from jizz.services.taxonomy_succession import reconcile_countries, reopen_countries

        salt = Species.objects.create(name='Saltmarsh Willet', name_latin='Tringa semipalmata', code='willet2')
        prairie = Species.objects.create(name='Prairie Willet', name_latin='Tringa inornata', code='willet3')
        Country.objects.get_or_create(code='US')
        Country.objects.get_or_create(code='US-CA')
        CountrySpecies.objects.create(country_id='US', species=salt)
        TaxonomyChange.objects.create(
            change_type='rename', old_codes=['willet1'], new_codes=['willet2'], status='applied',
            report={'kind': 'recode', 'species_id': salt.id, 'survivor_id': salt.id, 'targets': {'willet2': salt.id},
                    'country_removed_snapshot': [{'country_id': 'US-CA', 'species_id': salt.id, 'status': 'native',
                                                  'frequency': 'rare', 'frequency_pct': 3.0}]},
        )
        split = TaxonomyChange.objects.create(
            change_type='split', old_codes=['willet2'], new_codes=['willet2', 'willet3'], status='applied',
            report={'species_id': salt.id, 'survivor_id': salt.id, 'countries_pending': ['US'],
                    'targets': {'willet2': salt.id, 'willet3': prairie.id}, 'country_seeds': {}},
        )
        self.assertEqual(reopen_countries(split), 1)
        split.refresh_from_db()
        lists = {'US': ['willet2', 'willet3'], 'US-CA': ['willet3']}
        reconcile_countries(split, fetch=lambda c: lists[c])
        self.assertTrue(CountrySpecies.objects.filter(country_id='US-CA', species=prairie).exists())
        self.assertFalse(CountrySpecies.objects.filter(country_id='US-CA', species=salt).exists())
        self.assertTrue(CountrySpecies.objects.filter(country_id='US', species=prairie).exists())
