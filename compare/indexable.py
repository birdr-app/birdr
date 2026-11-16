"""Which species-comparison pages have real content, and in which languages.

A pair is also only worth a page when the two birds are plausible lookalikes. Most stored
pairs come from quiz mistakes, and a mistake can pair a lark with a cuckoo, so the rule is
that both species belong to the same taxonomic family. A pair someone chose on purpose, a
published community comparison, always counts.

A compare page only shows text when the cached AI comparison was built with the current
model and prompt (see ``comparison_cache_is_current``) or when a community comparison is
published. Everything else renders a "Writing a comparison…" placeholder, which is thin
content. The sitemap lists, and the page lets Google index, only pages this module accepts,
so the two can never disagree: a pair joins the sitemap the moment its comparison is
generated and leaves it when a prompt or model bump makes the stored text stale.
"""

from __future__ import annotations

from functools import reduce
from operator import or_

from django.db.models import F, Q, QuerySet

from compare.ai_service import HANDBOOK_MODEL, comparison_model_name, comparison_prompt_version
from compare.community import FORM_FIELDS
from compare.models import ComparisonTranslation, SpeciesComparison
from jizz.update_i18n import DEFAULT_LANGUAGE

TEXT_FIELDS = ('detailed_comparison', *(field for field, _label in FORM_FIELDS))


def current_comparisons() -> QuerySet[SpeciesComparison]:
    """Species comparisons the compare page renders: current model and prompt, with text.

    The same test as ``comparison_cache_is_current`` and ``has_comparison_text``, done in
    the database so a sitemap request does not load thousands of long texts.
    """
    has_text = reduce(or_, (Q(**{f'{field}__gt': ''}) for field in TEXT_FIELDS))
    return (
        SpeciesComparison.objects.filter(
            comparison_type='species',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        .exclude(ai_model=HANDBOOK_MODEL)
        .filter(has_text)
    )


def indexable_comparisons() -> QuerySet[SpeciesComparison]:
    """What the sitemap lists: real current text, and a sensible pair of birds."""
    return current_comparisons().filter(
        species_1__taxonomic_family__isnull=False,
        species_1__taxonomic_family_id=F('species_2__taxonomic_family_id'),
    )


def is_plausible_pair(species_a, species_b) -> bool:
    family = getattr(species_a, 'taxonomic_family_id', None)
    return bool(family) and family == getattr(species_b, 'taxonomic_family_id', None)


def translated_languages(comparison_ids) -> dict[int, set[str]]:
    """Comparison id -> languages with a stored translation that has text."""
    rows = (
        ComparisonTranslation.objects.filter(comparison_id__in=list(comparison_ids))
        .exclude(fields__summary='')
        .values_list('comparison_id', 'language')
    )
    found: dict[int, set[str]] = {}
    for comparison_id, language in rows:
        found.setdefault(comparison_id, set()).add(language)
    return found


def indexable_languages(
    comparison: SpeciesComparison | None,
    *,
    community: bool,
    all_languages,
    species_pair=None,
) -> set[str]:
    """Languages in which this pair's page has real content worth indexing.

    A published community comparison is shown as written whatever the language, so it
    counts in the default language only. An AI comparison counts in the default language
    and in every language it has been translated to.
    """
    from compare.community import has_comparison_text
    from compare.generation import comparison_cache_is_current

    if community:
        return {DEFAULT_LANGUAGE}
    if comparison is None or not comparison_cache_is_current(comparison) or not has_comparison_text(comparison):
        return set()
    if species_pair is not None and not is_plausible_pair(*species_pair):
        return set()
    translated = translated_languages([comparison.pk]).get(comparison.pk, set())
    return {DEFAULT_LANGUAGE} | (translated & set(all_languages))
