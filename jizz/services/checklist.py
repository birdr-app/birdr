"""
Aggregate per-country species checklist from games the user has played.

v1: all games for the country (see ``_qualifying_game_ids``).
Future: ``source=journey`` when Game is tagged with Motmot Journey.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import Count, F, Max, Q, QuerySet
from django.db.models.functions import Coalesce

from jizz.models import (
    Answer,
    Country,
    CountrySpecies,
    Player,
    PlayerScore,
    Species,
    SpeciesName,
    UserProfile,
)
from jizz.services.species_cover import species_cover_urls_bulk

VERY_RARE_FREQUENCIES = frozenset({'very_rare', 'vagrant'})

# Checklist only includes these CountrySpecies.status values (not introduced, escape, etc.).
CHECKLIST_COUNTRY_SPECIES_STATUSES = ('native', 'rare', 'endemic')

FREQUENCY_SORT_ORDER = {
    'abundant': 0,
    'very_common': 1,
    'common': 2,
    'fairly_common': 3,
    'uncommon': 4,
    'rare': 5,
    'very_rare': 6,
    'vagrant': 7,
}


@dataclass
class ChecklistParams:
    country_code: str | None
    status: str = 'all'
    tax_order: str | None = None
    sort: str = 'recent'
    search: str | None = None
    page: int = 1
    page_size: int = 50
    source: str = 'all_games'
    language: str = 'en'


def resolve_country(user, country_code: str | None) -> Country | None:
    code = (country_code or '').strip().upper()
    if not code:
        try:
            profile = user.profile
            if profile.country_id:
                return profile.country
        except UserProfile.DoesNotExist:
            pass
        return None
    try:
        return Country.objects.get(code__iexact=code)
    except Country.DoesNotExist:
        return None


def _country_species_qs(country: Country) -> QuerySet:
    return CountrySpecies.objects.filter(
        country=country,
        status__in=CHECKLIST_COUNTRY_SPECIES_STATUSES,
    )


def _player_scores_for_user(user, country: Country) -> QuerySet:
    player_ids = Player.objects.filter(user=user).values_list('id', flat=True)
    return PlayerScore.objects.filter(
        player_id__in=player_ids,
        game__country=country,
    )


def _qualifying_game_ids(scores: QuerySet, source: str) -> list[int]:
    if source == 'journey':
        # No Game.journey FK yet — journey-only checklist comes later.
        return []
    return list(scores.values_list('game_id', flat=True).distinct())


def _answered_answers_qs(game_ids: list[int], scores: QuerySet) -> QuerySet:
    """Answers the user submitted (correct or wrong); unanswered questions are excluded."""
    if not game_ids:
        return Answer.objects.none()
    return Answer.objects.filter(
        player_score__in=scores,
        question__game_id__in=game_ids,
    )


def _species_sets(game_ids: list[int], scores: QuerySet) -> tuple[set[int], set[int]]:
    """
    encountered: user answered a question targeting this species (right or wrong).
    identified: user ever chose the correct species for such a question (any game);
    later wrong answers on the same species do not remove it from identified.
    """
    if not game_ids:
        return set(), set()

    answers = _answered_answers_qs(game_ids, scores)
    encountered = set(answers.values_list('question__species_id', flat=True).distinct())
    identified = set(
        answers.filter(answer_id=F('question__species_id')).values_list(
            'question__species_id', flat=True
        ).distinct()
    )
    return encountered, identified


def resolve_checklist_user(player: Player, request=None):
    """Logged-in user from JWT/session or from the answering player's account link."""
    if request is not None:
        auth_user = getattr(request, 'user', None)
        if auth_user is not None and getattr(auth_user, 'is_authenticated', False):
            return auth_user
    if player.user_id:
        return player.user
    return None


def _checklist_feedback_context(player: Player, question, user=None, request=None):
    """(user_id, country_id, species_id) when species is checklist-eligible; else None."""
    resolved = user if user is not None else resolve_checklist_user(player, request)
    if resolved is None:
        return None
    game = question.game
    if not game.country_id:
        return None
    if not _country_species_qs(game.country).filter(species_id=question.species_id).exists():
        return None
    return resolved.id, game.country_id, question.species_id


def _user_identified_species(user_id: int, country_id: int, species_id: int) -> bool:
    return Answer.objects.filter(
        player_score__player__user_id=user_id,
        question__game__country_id=country_id,
        question__species_id=species_id,
        answer_id=F('question__species_id'),
    ).exists()


def _user_encountered_species(user_id: int, country_id: int, species_id: int) -> bool:
    return Answer.objects.filter(
        player_score__player__user_id=user_id,
        question__game__country_id=country_id,
        question__species_id=species_id,
    ).exists()


def compute_checklist_added(player: Player, question, correct: bool, user=None, request=None) -> bool:
    """
    True when a correct answer is the user's first identification of this species
    for the game's country (logged-in users only; species must be on the checklist).
    Call before persisting the new Answer row.
    """
    if not correct:
        return False
    ctx = _checklist_feedback_context(player, question, user=user, request=request)
    if ctx is None:
        return False
    user_id, country_id, species_id = ctx
    return not _user_identified_species(user_id, country_id, species_id)


def compute_checklist_missed(player: Player, question, correct: bool, user=None, request=None) -> bool:
    """
    True when a wrong answer is the user's first encounter with this checklist species
    for the game's country (logged-in users only; species not yet identified).
    Call before persisting the new Answer row.
    """
    if correct:
        return False
    ctx = _checklist_feedback_context(player, question, user=user, request=request)
    if ctx is None:
        return False
    user_id, country_id, species_id = ctx
    if _user_identified_species(user_id, country_id, species_id):
        return False
    return not _user_encountered_species(user_id, country_id, species_id)


def _compute_totals(
    country: Country,
    encountered: set[int],
    identified: set[int],
) -> dict[str, int]:
    checklist_ids = set(_country_species_qs(country).values_list('species_id', flat=True))
    encountered = encountered & checklist_ids
    identified = identified & checklist_ids
    cs_qs = _country_species_qs(country)
    total = cs_qs.count()
    identified_count = len(identified)
    missed_count = len(encountered - identified)
    unseen_count = total - len(encountered)
    very_rare_count = cs_qs.filter(frequency__in=VERY_RARE_FREQUENCIES).count()
    return {
        'all': total,
        'identified': identified_count,
        'missed': missed_count,
        'unseen': unseen_count,
        'very_rare': very_rare_count,
    }


def _next_milestone(identified: int, total: int) -> int | None:
    if total <= 0:
        return None
    if identified >= total:
        return total
    step = 50
    milestone = ((identified // step) + 1) * step
    return min(milestone, total)


def _progress_block(totals: dict[str, int]) -> dict[str, Any]:
    identified = totals['identified']
    total = totals['all']
    percent = round(100 * identified / total, 1) if total else 0.0
    return {
        'identified_count': identified,
        'total_count': total,
        'percent': percent,
        'next_milestone': _next_milestone(identified, total),
    }


def _status_for_species(species_id: int, encountered: set[int], identified: set[int]) -> str:
    if species_id in identified:
        return 'identified'
    if species_id in encountered:
        return 'missed'
    return 'unseen'


def _filter_country_species(
    cs_qs: QuerySet,
    status: str,
    encountered: set[int],
    identified: set[int],
) -> QuerySet:
    if status == 'identified':
        return cs_qs.filter(species_id__in=identified)
    if status == 'missed':
        missed = encountered - identified
        return cs_qs.filter(species_id__in=missed)
    if status == 'unseen':
        return cs_qs.exclude(species_id__in=encountered)
    if status == 'very_rare':
        return cs_qs.filter(frequency__in=VERY_RARE_FREQUENCIES)
    return cs_qs


def _annotate_species_stats(cs_qs: QuerySet, game_ids: list[int], scores: QuerySet) -> QuerySet:
    if not game_ids:
        return cs_qs

    answered_filter = Q(
        species__questions__game_id__in=game_ids,
        species__questions__answers__player_score__in=scores,
    )
    correct_filter = answered_filter & Q(
        species__questions__answers__answer_id=F('species__questions__species_id'),
    )
    return cs_qs.annotate(
        times_encountered=Count(
            'species__questions__answers',
            filter=answered_filter,
            distinct=True,
        ),
        times_identified=Count(
            'species__questions__answers',
            filter=correct_filter,
            distinct=True,
        ),
        last_encountered_at=Max(
            'species__questions__answers__created',
            filter=answered_filter,
        ),
        last_identified_at=Max(
            'species__questions__answers__created',
            filter=correct_filter,
        ),
    )


def _sort_queryset(cs_qs: QuerySet, sort: str, game_ids: list[int]) -> QuerySet:
    if sort in ('species', 'name'):
        return cs_qs.order_by('species_id')
    if sort == 'rarity':
        return cs_qs.order_by('-frequency', 'species_id')
    if game_ids:
        return cs_qs.order_by(
            Coalesce('last_identified_at', 'last_encountered_at').desc(nulls_last=True),
            'species_id',
        )
    return cs_qs.order_by('species_id')


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def normalize_species_language(language: str | None) -> str:
    """Normalize profile/UI codes (nl, NL, nl-NL) to SpeciesName language ids."""
    lang = (language or 'en').strip().lower()
    if not lang:
        return 'en'
    return lang.split('_')[0].split('-')[0] or 'en'


def _translated_names(species_ids: list[int], language: str) -> dict[int, str]:
    if not language or not species_ids:
        return {}
    language = normalize_species_language(language)
    names = SpeciesName.objects.filter(
        species_id__in=species_ids,
        language_id=language,
    ).values_list('species_id', 'name')
    return dict(names)


def localized_species_names(
    species_by_id: dict[int, Species],
    language: str | None,
) -> dict[int, str]:
    """Display names for species using the user's preferred language."""
    if not species_by_id:
        return {}
    language = normalize_species_language(language)
    if language.startswith('la'):
        return {
            sid: (sp.name_latin or sp.name)
            for sid, sp in species_by_id.items()
        }

    translated = _translated_names(list(species_by_id.keys()), language)
    out: dict[int, str] = {}
    for sid, sp in species_by_id.items():
        if sid in translated:
            out[sid] = translated[sid]
        elif language.startswith('nl') and sp.name_nl:
            out[sid] = sp.name_nl
        else:
            out[sid] = sp.name
    return out


def _tax_order_filters(country: Country) -> list[dict[str, Any]]:
    rows = (
        _country_species_qs(country)
        .exclude(species__taxonomic_order__isnull=True)
        .values('species__taxonomic_order__name_latin')
        .annotate(count=Count('id'))
        .order_by('species__taxonomic_order__name_latin')
    )
    return [
        {'tax_order': r['species__taxonomic_order__name_latin'], 'count': r['count']}
        for r in rows
    ]


def build_checklist(user, params: ChecklistParams, request=None) -> dict[str, Any]:
    country = resolve_country(user, params.country_code)
    if not country:
        return {'error': 'no_country'}

    scores = _player_scores_for_user(user, country)
    game_ids = _qualifying_game_ids(scores, params.source)
    encountered, identified = _species_sets(game_ids, scores)
    checklist_ids = set(_country_species_qs(country).values_list('species_id', flat=True))
    encountered &= checklist_ids
    identified &= checklist_ids
    totals = _compute_totals(country, encountered, identified)

    cs_qs = _country_species_qs(country).select_related('species')
    if params.tax_order:
        cs_qs = cs_qs.filter(species__taxonomic_order__name_latin=params.tax_order)
    if params.search:
        q = params.search.strip()
        if q:
            cs_qs = cs_qs.filter(
                Q(species__name__icontains=q)
                | Q(species__name_latin__icontains=q)
                | Q(species__code__icontains=q)
            )

    cs_qs = _filter_country_species(cs_qs, params.status, encountered, identified)
    cs_qs = _annotate_species_stats(cs_qs, game_ids, scores)
    cs_qs = _sort_queryset(cs_qs, params.sort, game_ids)

    page_size = max(1, min(params.page_size, 100))
    page = max(1, params.page)
    total_filtered = cs_qs.count()
    start = (page - 1) * page_size
    page_rows = list(cs_qs[start : start + page_size])

    species_ids = [row.species_id for row in page_rows]
    ill_map = species_cover_urls_bulk(species_ids, request)
    name_map = _translated_names(species_ids, params.language)

    species_payload = []
    for row in page_rows:
        sp = row.species
        sid = sp.id
        species_payload.append({
            'id': sid,
            'code': sp.code,
            'name': sp.name,
            'name_latin': sp.name_latin,
            'name_nl': sp.name_nl,
            'name_translated': name_map.get(sid) or sp.name,
            'tax_order': sp.tax_order,
            'status': _status_for_species(sid, encountered, identified),
            'frequency': row.frequency,
            'times_encountered': getattr(row, 'times_encountered', 0) or 0,
            'times_identified': getattr(row, 'times_identified', 0) or 0,
            'last_encountered_at': _iso_datetime(getattr(row, 'last_encountered_at', None)),
            'last_identified_at': _iso_datetime(getattr(row, 'last_identified_at', None)),
            'illustration_url': ill_map.get(sid),
        })

    return {
        'country': {'code': country.code, 'name': country.name},
        'totals': totals,
        'progress': _progress_block(totals),
        'tax_orders': _tax_order_filters(country),
        'species': species_payload,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total_filtered,
            'has_next': start + page_size < total_filtered,
        },
        'source': params.source,
    }
