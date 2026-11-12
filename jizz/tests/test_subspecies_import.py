from django.test import TestCase

from jizz.models import Species, SpeciesAlias, Subspecies, resolve_species_by_code
from jizz.services.taxonomy_sync import import_subspecies


def _row(code, report_as, category='issf', name='Form', sci='Genus species form', order=1.0):
    return {
        'category': category,
        'speciesCode': code,
        'reportAs': report_as,
        'comName': name,
        'sciName': sci,
        'taxonOrder': order,
    }


class ImportSubspeciesTests(TestCase):
    def setUp(self):
        self.redpoll = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='comred')

    def test_creates_subspecies_under_parent(self):
        stats = import_subspecies([_row('comred1', 'comred', name='Mealy Redpoll')])
        self.assertEqual(stats['created'], 1)
        sub = Subspecies.objects.get(code='comred1')
        self.assertEqual(sub.species, self.redpoll)
        self.assertEqual(sub.name, 'Mealy Redpoll')
        self.assertTrue(sub.active)

    def test_ignores_species_rows_and_counts_orphans(self):
        stats = import_subspecies([
            {'category': 'species', 'speciesCode': 'x', 'reportAs': None},
            _row('lost1', 'unknown'),
        ])
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['orphan'], 1)
        self.assertEqual(Subspecies.objects.count(), 0)

    def test_update_and_unchanged(self):
        import_subspecies([_row('comred1', 'comred', name='Old')])
        stats = import_subspecies([_row('comred1', 'comred', name='New')])
        self.assertEqual(stats['updated'], 1)
        self.assertEqual(Subspecies.objects.get(code='comred1').name, 'New')
        stats = import_subspecies([_row('comred1', 'comred', name='New')])
        self.assertEqual(stats['unchanged'], 1)

    def test_missing_from_feed_is_deactivated_not_deleted(self):
        import_subspecies([_row('comred1', 'comred')])
        stats = import_subspecies([])
        self.assertEqual(stats['deactivated'], 1)
        self.assertFalse(Subspecies.objects.get(code='comred1').active)

    def test_lump_rows_are_never_touched(self):
        lumped = Subspecies.objects.create(
            species=self.redpoll, code='hoared', name='Hoary Redpoll',
            source=Subspecies.SOURCE_LUMP, former_species_id=99,
        )
        stats = import_subspecies([_row('hoared', 'comred', name='Changed')])
        self.assertEqual(stats['unchanged'], 1)
        lumped.refresh_from_db()
        self.assertEqual(lumped.name, 'Hoary Redpoll')
        # and a feed that omits it does not deactivate it
        import_subspecies([])
        lumped.refresh_from_db()
        self.assertTrue(lumped.active)

    def test_dry_run_writes_nothing(self):
        stats = import_subspecies([_row('comred1', 'comred')], dry_run=True)
        self.assertEqual(stats['created'], 1)
        self.assertEqual(Subspecies.objects.count(), 0)


class ResolveSpeciesByCodeTests(TestCase):
    def test_current_code_alias_and_unknown(self):
        survivor = Species.objects.create(name='Redpoll', name_latin='Acanthis flammea', code='comred')
        SpeciesAlias.objects.create(code='hoared', species=survivor, reason=SpeciesAlias.REASON_LUMP)
        self.assertEqual(resolve_species_by_code('comred'), survivor)
        self.assertEqual(resolve_species_by_code('hoared'), survivor)
        self.assertIsNone(resolve_species_by_code('nope'))
        self.assertIsNone(resolve_species_by_code(''))
