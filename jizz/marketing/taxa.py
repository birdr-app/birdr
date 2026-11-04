"""Public pages for bird orders, families and birder groups (shorebirds, wood-warblers)."""

from __future__ import annotations

from django.core.cache import cache
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify

from compare.models import SpeciesComparison
from jizz.marketing.i18n import locale_from_request, translate
from jizz.marketing.local_names import species_display_names, taxonomy_display_name
from jizz.marketing.pages import (
    MARKETING_QUERY_CACHE_TTL,
    SITE_HOME,
    base_context,
    public_species_ids,
)
from jizz.marketing.slugs import compare_pair_slug
from jizz.models import Species, SpeciesGroup, TaxonomicFamily, TaxonomicOrder
from jizz.services.species_groups import group_name_for_locale

# A group page with a single species adds nothing over that species' page.
MIN_GROUP_SPECIES = 2
MAX_COMPARISONS = 24


def _counts(field: str) -> dict[int, int]:
    return dict(
        Species.objects.filter(id__in=public_species_ids())
        .values(field)
        .annotate(n=Count('id'))
        .values_list(field, 'n')
    )


def taxa_index() -> dict:
    """Orders with their families, and groups, each with its public species count."""
    cached = cache.get('marketing-taxa-v1')
    if cached is not None:
        return cached
    family_counts = _counts('taxonomic_family_id')
    group_counts = _counts('species_group_id')
    families_by_order: dict[int | None, list[dict]] = {}
    for family in TaxonomicFamily.objects.all():
        count = family_counts.get(family.id, 0)
        if not count:
            continue
        families_by_order.setdefault(family.taxonomic_order_id, []).append({
            'id': family.id,
            'latin': family.name_latin,
            'name_en': family.name_en,
            'name_nl': family.name_nl,
            'count': count,
            'url': reverse('marketing-family', kwargs={'slug': slugify(family.name_latin)}),
        })
    orders = []
    for order in TaxonomicOrder.objects.all():
        families = families_by_order.get(order.id, [])
        if not families:
            continue
        orders.append({
            'id': order.id,
            'latin': order.name_latin,
            'name_en': order.name_en,
            'name_nl': order.name_nl,
            'count': sum(f['count'] for f in families),
            'url': reverse('marketing-order', kwargs={'slug': slugify(order.name_latin)}),
            'families': families,
        })
    groups = []
    for group in SpeciesGroup.objects.all():
        count = group_counts.get(group.id, 0)
        if count < MIN_GROUP_SPECIES:
            continue
        groups.append({
            'id': group.id,
            'slug': group.slug,
            'names': {
                field: getattr(group, field)
                for field in ('name_en', 'name_nl', 'name_es', 'name_fr', 'name_de', 'name_it', 'name_pt_br', 'name_ja')
            },
            'count': count,
            'url': reverse('marketing-group', kwargs={'slug': group.slug}),
        })
    data = {'orders': orders, 'groups': groups}
    cache.set('marketing-taxa-v1', data, MARKETING_QUERY_CACHE_TTL)
    return data


def taxa_paths() -> list[str]:
    data = taxa_index()
    paths = [reverse('marketing-orders'), reverse('marketing-groups')]
    for order in data['orders']:
        paths.append(order['url'])
        paths.extend(family['url'] for family in order['families'])
    paths.extend(group['url'] for group in data['groups'])
    return paths


def _taxon_name(row: dict, locale: str) -> str:
    return taxonomy_display_name(row['name_en'], row['name_nl'], locale) or row['latin']


def _group_name(row: dict, locale: str) -> str:
    return group_name_for_locale(row['names'], locale)


def _description(obj, locale: str) -> str:
    if locale == 'nl' and obj.description_nl:
        return obj.description_nl
    return obj.description_en or ''


def _species_rows(qs, locale: str) -> list[dict]:
    rows = list(qs.filter(id__in=public_species_ids()).order_by('name_latin').values('id', 'slug', 'name', 'name_latin'))
    names = species_display_names([row['id'] for row in rows], locale)
    for row in rows:
        row['display_name'] = names.get(row['id']) or row['name']
    return rows


def _comparison_rows(species_ids: list[int], locale: str) -> list[dict]:
    """AI comparisons between two species of the same taxon, for links to the compare pages."""
    pairs = list(
        SpeciesComparison.objects.filter(
            comparison_type='species',
            species_1_id__in=species_ids,
            species_2_id__in=species_ids,
        )
        .exclude(Q(summary='') | Q(summary__isnull=True))
        .values_list('species_1_id', 'species_2_id')[:MAX_COMPARISONS]
    )
    ids = {pk for pair in pairs for pk in pair}
    slugs = dict(Species.objects.filter(id__in=ids).values_list('id', 'slug'))
    names = species_display_names(ids, locale)
    rows = []
    for a, b in pairs:
        low, high = sorted((a, b))
        if not slugs.get(low) or not slugs.get(high):
            continue
        rows.append({
            'url': reverse('marketing-compare', kwargs={'pair': compare_pair_slug(slugs[low], slugs[high])}),
            'low_name': names.get(low, ''),
            'high_name': names.get(high, ''),
        })
    rows.sort(key=lambda r: (r['low_name'].casefold(), r['high_name'].casefold()))
    return rows


def orders_index(request):
    locale = locale_from_request(request)
    path = reverse('marketing-orders')
    orders = []
    for order in taxa_index()['orders']:
        orders.append({
            **order,
            'name': _taxon_name(order, locale),
            'families': [
                {**family, 'name': f"{_taxon_name(family, locale)} ({family['count']})"}
                for family in order['families']
            ],
        })
    context = base_context(
        request,
        title=translate('Bird Orders and Families | Motmot'),
        description=translate(
            'Browse every bird order and family on Motmot, with species pages, identification tips and quizzes.'
        ),
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Species', reverse('marketing-birds')), ('Bird orders and families', path)],
        orders=orders,
    )
    return render(request, 'marketing/taxa_index.html', context)


def groups_index(request):
    locale = locale_from_request(request)
    path = reverse('marketing-groups')
    groups = [
        {**group, 'name': f"{_group_name(group, locale)} ({group['count']})"}
        for group in taxa_index()['groups']
    ]
    groups.sort(key=lambda g: g['name'].casefold())
    context = base_context(
        request,
        title=translate('Bird Groups | Motmot'),
        description=translate(
            'Browse birds by group, from shorebirds to wood-warblers, with species pages, identification tips and quizzes.'
        ),
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Species', reverse('marketing-birds')), ('Bird groups', path)],
        groups=groups,
    )
    return render(request, 'marketing/taxa_index.html', context)


def _find(rows: list[dict], url: str) -> dict:
    row = next((r for r in rows if r['url'] == url), None)
    if row is None:
        raise Http404()
    return row


def order_page(request, slug: str):
    locale = locale_from_request(request)
    path = reverse('marketing-order', kwargs={'slug': slug})
    row = _find(taxa_index()['orders'], path)
    order = TaxonomicOrder.objects.get(id=row['id'])
    name = _taxon_name(row, locale)
    families = [
        {**family, 'name': f"{_taxon_name(family, locale)} ({family['count']})"}
        for family in row['families']
    ]
    return _taxon_response(
        request,
        kind='order',
        name=name,
        latin=order.name_latin,
        count=row['count'],
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Bird orders and families', reverse('marketing-orders')), (name, path)],
        description_text=_description(order, locale),
        children=families,
    )


def family_page(request, slug: str):
    locale = locale_from_request(request)
    path = reverse('marketing-family', kwargs={'slug': slug})
    index = taxa_index()
    order_row = next((o for o in index['orders'] if any(f['url'] == path for f in o['families'])), None)
    if order_row is None:
        raise Http404()
    row = _find(order_row['families'], path)
    family = TaxonomicFamily.objects.get(id=row['id'])
    name = _taxon_name(row, locale)
    order_name = _taxon_name(order_row, locale)
    species = _species_rows(Species.objects.filter(taxonomic_family=family), locale)
    return _taxon_response(
        request,
        kind='family',
        name=name,
        latin=family.name_latin,
        count=row['count'],
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Bird orders and families', reverse('marketing-orders')),
            (order_name, order_row['url']),
            (name, path),
        ],
        description_text=_description(family, locale),
        parent_name=order_name,
        parent_href=order_row['url'],
        species_rows=species,
        comparisons=_comparison_rows([s['id'] for s in species], locale),
    )


def group_page(request, slug: str):
    locale = locale_from_request(request)
    path = reverse('marketing-group', kwargs={'slug': slug})
    row = _find(taxa_index()['groups'], path)
    name = _group_name(row, locale)
    species = _species_rows(Species.objects.filter(species_group_id=row['id']), locale)
    return _taxon_response(
        request,
        kind='group',
        name=name,
        latin='',
        count=row['count'],
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Bird groups', reverse('marketing-groups')), (name, path)],
        description_text='',
        species_rows=species,
        comparisons=_comparison_rows([s['id'] for s in species], locale),
    )


def _taxon_response(request, *, kind, name, latin, count, path, breadcrumbs, **extra):
    # Orders often have no common name, so the Latin name would show twice.
    if latin.casefold() == name.casefold():
        latin = ''
    if latin:
        title = translate(
            '{name} ({latin}) – Bird Order | Motmot' if kind == 'order' else '{name} ({latin}) – Bird Family | Motmot',
            name=name,
            latin=latin,
        )
        description = translate(
            '{name} ({latin}) on Motmot: {count} species with photos, identification tips and quizzes.',
            name=name,
            latin=latin,
            count=count,
        )
    else:
        title = translate(
            {
                'order': '{name} – Bird Order | Motmot',
                'family': '{name} – Bird Family | Motmot',
            }.get(kind, '{name} – Bird Group | Motmot'),
            name=name,
        )
        description = translate(
            '{name} on Motmot: {count} species with photos, identification tips and quizzes.',
            name=name,
            count=count,
        )
    context = base_context(
        request,
        title=title,
        description=description,
        path=path,
        breadcrumbs=breadcrumbs,
        kind=kind,
        taxon_name=name,
        taxon_latin=latin,
        species_count=count,
        quiz_href='/play',
        **extra,
    )
    return render(request, 'marketing/taxon.html', context)


def taxon_links(species, locale: str) -> dict:
    """Family, order and group page URLs for a species, when those pages exist."""
    index = taxa_index()
    out = {}
    for order in index['orders']:
        for family in order['families']:
            if family['id'] == species.taxonomic_family_id:
                out['family_href'] = family['url']
                out['order_href'] = order['url']
    group = next((g for g in index['groups'] if g['id'] == species.species_group_id), None)
    if group:
        out['group_name'] = _group_name(group, locale)
        out['group_href'] = group['url']
    return out
