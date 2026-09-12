from jizz.models import Species, SpeciesGroup, TaxonomicFamily, TaxonomicGenus, TaxonomicOrder


def make_taxonomic_order(name_latin, name_en=None, name_nl=None):
    name_en = name_en or name_latin
    name_nl = name_nl or name_en
    return TaxonomicOrder.objects.create(
        name_latin=name_latin,
        name_en=name_en,
        name_nl=name_nl,
    )


def make_taxonomic_family(name_latin, name_en=None, name_nl=None, taxonomic_order=None):
    name_en = name_en or name_latin
    name_nl = name_nl or name_en
    return TaxonomicFamily.objects.create(
        name_latin=name_latin,
        name_en=name_en,
        name_nl=name_nl,
        taxonomic_order=taxonomic_order,
    )


def make_taxonomic_genus(name_latin, taxonomic_family=None, name_en=None, name_nl=None):
    name_en = name_en or name_latin
    name_nl = name_nl or name_en
    return TaxonomicGenus.objects.create(
        name_latin=name_latin,
        name_en=name_en,
        name_nl=name_nl,
        taxonomic_family=taxonomic_family,
    )


def make_species_group(slug, name_en=None, name_nl=None, ebird_name=None, sort_order=0):
    name_en = name_en or slug.replace('-', ' ').title()
    name_nl = name_nl or name_en
    return SpeciesGroup.objects.create(
        slug=slug,
        ebird_name=ebird_name or name_en,
        name_en=name_en,
        name_nl=name_nl,
        sort_order=sort_order,
    )


def make_species_with_taxonomy(
    *,
    name,
    name_latin,
    code,
    tax_order=None,
    tax_family=None,
    tax_family_en=None,
    tax_genus=None,
    name_nl=None,
    tax_ordering=None,
    species_group=None,
    **kwargs,
):
    taxonomic_order = None
    taxonomic_family = None
    taxonomic_genus = None
    if tax_order:
        taxonomic_order, _ = TaxonomicOrder.objects.get_or_create(
            name_latin=tax_order,
            defaults={'name_en': tax_order, 'name_nl': tax_order},
        )
    if tax_family:
        family_defaults = {
            'name_en': tax_family_en or tax_family,
            'name_nl': tax_family_en or tax_family,
            'taxonomic_order': taxonomic_order,
        }
        taxonomic_family, _ = TaxonomicFamily.objects.get_or_create(
            name_latin=tax_family,
            defaults=family_defaults,
        )
    if tax_genus:
        taxonomic_genus, _ = TaxonomicGenus.objects.get_or_create(
            name_latin=tax_genus,
            defaults={
                'name_en': tax_genus,
                'name_nl': tax_genus,
                'taxonomic_family': taxonomic_family,
            },
        )
    return Species.objects.create(
        name=name,
        name_latin=name_latin,
        code=code,
        name_nl=name_nl,
        taxonomic_order=taxonomic_order,
        taxonomic_family=taxonomic_family,
        taxonomic_genus=taxonomic_genus,
        species_group=species_group,
        tax_ordering=tax_ordering,
        **kwargs,
    )
