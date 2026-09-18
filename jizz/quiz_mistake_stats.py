"""
Aggregates for quiz mistake analytics (public data pages).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from io import StringIO
from typing import Any

from django.core.cache import cache
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Greatest, Least
from django.http import HttpRequest, HttpResponse

from jizz.models import Answer, Country, CountrySpecies, Question, QuestionOption, Species

# Include a species only when it was picked at least this many times (all countries).
MIN_TIMES_SHOWN = 10
# Country-filtered views use a lower bar — per-country sample sizes are smaller.
MIN_TIMES_SHOWN_COUNTRY = 3

# When filtering by country, exclude CountrySpecies rows with these statuses for that country.
EXCLUDED_COUNTRY_SPECIES_STATUSES = frozenset(("introduced", "uncertain", "unknown"))

# Personal trouble-spots thresholds (sparse per-user data).
USER_MIN_TIMES_SHOWN = 2
USER_MIN_WRONG = 1
USER_MIN_PAIR_WRONG = 2
# Practice games with at least this many correct answers mark the target as fixed.
PAIR_PRACTICE_PASS_CORRECT = 18
SPECIES_PRACTICE_PASS_CORRECT = PAIR_PRACTICE_PASS_CORRECT

# Data-site HTML/CSV; marketing pages keep their own longer TTL.
MISTAKE_STATS_CACHE_TTL = 15 * 60


def _allowed_species_ids_for_country(country_code: str) -> frozenset[int]:
    """Species that have a non-excluded status for this country in CountrySpecies."""
    return frozenset(
        CountrySpecies.objects.filter(country_id=country_code)
        .exclude(status__in=EXCLUDED_COUNTRY_SPECIES_STATUSES)
        .values_list("species_id", flat=True)
    )


def normalize_country_filter(country_code: str | None) -> str | None:
    """Return a valid Country primary key (code) or None for all countries."""
    if country_code is None or not str(country_code).strip():
        return None
    code = str(country_code).strip().upper()
    if Country.objects.filter(pk=code).exists():
        return code
    return None


def min_times_shown_for_filter(country_code: str | None = None) -> int:
    return MIN_TIMES_SHOWN_COUNTRY if normalize_country_filter(country_code) else MIN_TIMES_SHOWN


def _error_rate_pct(wrong: int, correct: int) -> float | None:
    """% wrong among attempts where this species was chosen: wrong / (wrong + correct)."""
    denom = wrong + correct
    if denom <= 0:
        return None
    return 100.0 * wrong / denom


def _target_success_rate_pct(correct: int, times_shown: int) -> float | None:
    """% correct when this species was the question target: correct / times_shown."""
    if times_shown <= 0:
        return None
    return 100.0 * correct / times_shown


def _target_error_rate_pct(wrong: int, times_shown: int) -> float | None:
    """% wrong when this species was the question target: wrong / times_shown."""
    if times_shown <= 0:
        return None
    return 100.0 * wrong / times_shown


def _user_answers_qs(user_id: int):
    return Answer.objects.filter(player_score__player__user_id=user_id)


def get_species_mistake_rows(country_code: str | None = None) -> list[dict[str, Any]]:
    """
    Per species (only when the player explicitly picked the species):

    - times_shown: answers where the player picked this species (correct or incorrect).
    - correctly_answered / wrongly_answered: answers where the player picked this species.
    - error_rate: % wrong among picks of this species = wrong / (wrong + correct).

    If country_code is set, only answers from games in that country are counted,
    and only for species on that country's checklist (CountrySpecies excludes
    introduced / uncertain / unknown). Uses a lower minimum pick count than the
    global view (see min_times_shown_for_filter).
    """
    cc = normalize_country_filter(country_code)
    min_picks = min_times_shown_for_filter(country_code)
    answers = Answer.objects.all()
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return []
        answers = answers.filter(
            question__game__country_id=cc,
            answer_id__in=allowed,
        )

    aggregated = list(
        answers.values("answer_id").annotate(
            times_shown=Count("id"),
            correctly_answered=Count("id", filter=Q(correct=True)),
            wrongly_answered=Count("id", filter=Q(correct=False)),
        )
    )
    ids = {row["answer_id"] for row in aggregated if row["answer_id"] is not None}
    if not ids:
        return []

    species_map = Species.objects.in_bulk(ids)

    rows: list[dict[str, Any]] = []
    for row in aggregated:
        sid = row["answer_id"]
        if sid is None:
            continue
        ts = row["times_shown"]
        if ts < min_picks:
            continue
        sp = species_map.get(sid)
        if sp is None:
            continue
        cor = row["correctly_answered"]
        wr = row["wrongly_answered"]
        rows.append(
            {
                "species_id": sid,
                "name": sp.name,
                "name_latin": sp.name_latin,
                "times_shown": ts,
                "correctly_answered": cor,
                "wrongly_answered": wr,
                "error_rate": _error_rate_pct(wr, cor),
            }
        )
    return rows


def sort_species_rows(
    rows: list[dict[str, Any]], sort_key: str, descending: bool = True
) -> list[dict[str, Any]]:
    """sort_key: error_rate | times_shown — None error_rate sorts last when descending."""

    def sort_value(row: dict[str, Any]) -> float:
        if sort_key == "times_shown":
            return float(row["times_shown"])
        r = row["error_rate"]
        if r is None:
            return float("-inf") if descending else float("inf")
        return r

    return sorted(rows, key=sort_value, reverse=descending)


def get_top_mistake_species_ids(country_code: str | None, *, limit: int = 100) -> list[int]:
    """
    Species IDs most often picked wrong (answer_id), for the data/quiz-mistakes page.
    """
    rows = get_species_mistake_rows(country_code)
    rows.sort(
        key=lambda row: (row["wrongly_answered"], row["error_rate"] or 0.0),
        reverse=True,
    )
    return [row["species_id"] for row in rows[:limit]]


def get_top_mistake_target_species_ids(
    country_code: str | None,
    *,
    limit: int = 100,
    min_wrong: int | None = None,
) -> list[int]:
    """
    Species most often answered wrong when they were the question target.

    Uses the same country game + checklist filter as get_species_mistake_rows,
    but counts misses (correct=False, question.species) rather than wrong picks (answer_id).
    Used for Game.dificult_species question selection.
    """
    cc = normalize_country_filter(country_code)
    threshold = min_wrong if min_wrong is not None else min_times_shown_for_filter(country_code)

    wrong_answers = Answer.objects.filter(correct=False)
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return []
        wrong_answers = wrong_answers.filter(
            question__game__country_id=cc,
            question__species_id__in=allowed,
        )

    rows = list(
        wrong_answers.values("question__species_id")
        .annotate(wrongly_answered=Count("id"))
        .filter(wrongly_answered__gte=threshold)
        .order_by("-wrongly_answered")
    )
    return [row["question__species_id"] for row in rows[:limit]]


def get_user_mistake_target_weights(
    country_code: str | None,
    *,
    player_id: int | None,
    user_id: int | None,
) -> dict[int, int]:
    """
    Wrong-answer counts per question-target species for one player or user account.

    Used for extreme game question selection (personalized mistake weighting).
    """
    if not player_id and not user_id:
        return {}

    wrong_answers = Answer.objects.filter(correct=False)
    if user_id:
        wrong_answers = wrong_answers.filter(player_score__player__user_id=user_id)
    else:
        wrong_answers = wrong_answers.filter(player_score__player_id=player_id)

    cc = normalize_country_filter(country_code)
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return {}
        wrong_answers = wrong_answers.filter(question__species_id__in=allowed)

    return {
        row["question__species_id"]: row["wrongly_answered"]
        for row in wrong_answers.values("question__species_id")
        .annotate(wrongly_answered=Count("id"))
        .filter(question__species_id__isnull=False)
    }


def get_wrong_pick_weights_for_target(
    target_species_id: int,
    *,
    country_code: str | None = None,
    player_id: int | None = None,
    user_id: int | None = None,
) -> dict[int, int]:
    """
    Wrong-answer counts per picked species when target_species_id was the question.

    Omit player_id and user_id to aggregate across all players.
    """
    if not target_species_id:
        return {}

    wrong_answers = Answer.objects.filter(
        correct=False,
        question__species_id=target_species_id,
    ).exclude(answer_id=target_species_id)

    if user_id:
        wrong_answers = wrong_answers.filter(player_score__player__user_id=user_id)
    elif player_id:
        wrong_answers = wrong_answers.filter(player_score__player_id=player_id)

    cc = normalize_country_filter(country_code)
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return {}
        wrong_answers = wrong_answers.filter(answer_id__in=allowed)

    return {
        row["answer_id"]: row["c"]
        for row in wrong_answers.values("answer_id")
        .annotate(c=Count("id"))
        .filter(answer_id__isnull=False)
    }


def get_user_wrong_pick_weights_for_target(
    target_species_id: int,
    *,
    country_code: str | None = None,
    player_id: int | None = None,
    user_id: int | None = None,
) -> dict[int, int]:
    """Wrong picks for one player or user account (species-practice personalization)."""
    if not player_id and not user_id:
        return {}
    return get_wrong_pick_weights_for_target(
        target_species_id,
        country_code=country_code,
        player_id=player_id,
        user_id=user_id,
    )


def get_user_trouble_spot_rows(
    user_id: int,
    country_code: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Species mistake rows and confusion pair rows for one user in a single Answer scan.
    """
    if not user_id:
        return [], []

    cc = normalize_country_filter(country_code)
    allowed: frozenset[int] | None = None
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return [], []

    answers = _user_answers_qs(user_id).values_list(
        'question__species_id',
        'answer_id',
        'correct',
    )
    if allowed is not None:
        answers = answers.filter(
            question__species_id__in=allowed,
            answer_id__in=allowed,
        )

    species_times: dict[int, int] = defaultdict(int)
    species_wrong: dict[int, int] = defaultdict(int)
    pair_map: dict[tuple[int, int], dict[str, Any]] = {}

    for target_id, pick_id, correct in answers.iterator(chunk_size=2000):
        if target_id is None:
            continue
        species_times[target_id] += 1
        if not correct:
            species_wrong[target_id] += 1
            if pick_id is not None and pick_id != target_id:
                low_id, high_id = (
                    (target_id, pick_id) if target_id < pick_id else (pick_id, target_id)
                )
                key = (low_id, high_id)
                if key not in pair_map:
                    pair_map[key] = {
                        'low_id': low_id,
                        'high_id': high_id,
                        'total_wrong': 0,
                        'when_low_was_target': 0,
                        'when_high_was_target': 0,
                    }
                bucket = pair_map[key]
                bucket['total_wrong'] += 1
                if target_id == low_id:
                    bucket['when_low_was_target'] += 1
                else:
                    bucket['when_high_was_target'] += 1

    species_ids = set(species_times) | set(species_wrong)
    species_map = Species.objects.in_bulk(species_ids) if species_ids else {}

    species_rows: list[dict[str, Any]] = []
    for sid in species_ids:
        sp = species_map.get(sid)
        if sp is None:
            continue
        ts = species_times.get(sid, 0)
        wr = species_wrong.get(sid, 0)
        if ts < USER_MIN_TIMES_SHOWN or wr < USER_MIN_WRONG:
            continue
        cor = ts - wr
        species_rows.append(
            {
                'species_id': sid,
                'name': sp.name,
                'name_latin': sp.name_latin,
                'times_shown': ts,
                'correctly_answered': cor,
                'wrongly_answered': wr,
                'correct_rate': _target_success_rate_pct(cor, ts),
                'error_rate': _target_error_rate_pct(wr, ts),
            }
        )
    species_rows.sort(
        key=lambda r: (r['error_rate'] or 0.0, r['wrongly_answered']),
        reverse=True,
    )

    pair_ids = {i for key in pair_map for i in key}
    pair_species_map = Species.objects.in_bulk(pair_ids) if pair_ids else {}

    pair_rows: list[dict[str, Any]] = []
    for bucket in pair_map.values():
        if bucket['total_wrong'] < USER_MIN_PAIR_WRONG:
            continue
        low = pair_species_map.get(bucket['low_id'])
        high = pair_species_map.get(bucket['high_id'])
        pair_rows.append(
            {
                **bucket,
                'low_name': low.name if low else '',
                'high_name': high.name if high else '',
                'low_name_latin': low.name_latin if low else '',
                'high_name_latin': high.name_latin if high else '',
            }
        )
    pair_rows.sort(key=lambda r: r['total_wrong'], reverse=True)
    return species_rows, pair_rows


def get_user_species_mistake_rows(
    user_id: int,
    country_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    Per question-target species for one user account.

    - times_shown: answers to questions where this species was the target.
    - wrongly_answered: incorrect answers on those questions.
    - error_rate: % wrong = wrongly_answered / times_shown.

    Sorted by error_rate desc, then wrongly_answered desc.
    """
    species_rows, _ = get_user_trouble_spot_rows(user_id, country_code)
    return species_rows


def get_confusion_partner_species_ids(
    species_id: int,
    *,
    country_code: str | None = None,
    user_id: int | None = None,
) -> set[int]:
    """Other species appearing in confusion pairs with species_id (user + global)."""
    if not species_id:
        return set()

    partners: set[int] = set()
    if user_id:
        for row in get_user_confusion_pair_rows(user_id, country_code):
            if row['low_id'] == species_id:
                partners.add(row['high_id'])
            elif row['high_id'] == species_id:
                partners.add(row['low_id'])

    for row in get_confusion_pair_rows(country_code):
        if row['low_id'] == species_id:
            partners.add(row['high_id'])
        elif row['high_id'] == species_id:
            partners.add(row['low_id'])

    return partners


def get_user_confusion_pair_rows(
    user_id: int,
    country_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    Undirected species pairs from a user's incorrect answers (target != pick).

    Same shape as get_confusion_pair_rows(); includes pairs with total_wrong >= USER_MIN_PAIR_WRONG.
    """
    _, pair_rows = get_user_trouble_spot_rows(user_id, country_code)
    return pair_rows


def get_user_fixed_confusion_pair_keys(user_id: int) -> set[tuple[int, int]]:
    """Canonical (low_id, high_id) pairs the user fixed via a successful pair-practice game."""
    if not user_id:
        return set()

    from jizz.models import Game

    done_questions = (
        Question.objects.filter(game_id=OuterRef('pk'), done=True)
        .order_by()
        .values('game_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    correct_answers = (
        Answer.objects.filter(
            player_score__game_id=OuterRef('pk'),
            player_score__player__user_id=user_id,
            correct=True,
        )
        .order_by()
        .values('player_score__game_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )

    rows = (
        Game.objects.filter(
            game_type=Game.GAME_TYPE_PAIR_PRACTICE,
            host__user_id=user_id,
        )
        .exclude(pair_species_low_id__isnull=True)
        .exclude(pair_species_high_id__isnull=True)
        .annotate(
            done_questions=Coalesce(Subquery(done_questions, output_field=IntegerField()), 0),
            correct_answers=Coalesce(Subquery(correct_answers, output_field=IntegerField()), 0),
        )
        .filter(
            Q(force_ended=True) | Q(done_questions__gte=F('length')),
            correct_answers__gte=PAIR_PRACTICE_PASS_CORRECT,
        )
        .values_list('pair_species_low_id', 'pair_species_high_id')
    )
    return {tuple(row) for row in rows}


def get_user_fixed_species_ids(user_id: int) -> set[int]:
    """Species ids the user fixed via a successful species-practice game."""
    if not user_id:
        return set()

    from jizz.models import Game

    done_questions = (
        Question.objects.filter(game_id=OuterRef('pk'), done=True)
        .order_by()
        .values('game_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    correct_answers = (
        Answer.objects.filter(
            player_score__game_id=OuterRef('pk'),
            player_score__player__user_id=user_id,
            correct=True,
        )
        .order_by()
        .values('player_score__game_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )

    rows = (
        Game.objects.filter(
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            host__user_id=user_id,
        )
        .exclude(focus_species_id__isnull=True)
        .annotate(
            done_questions=Coalesce(Subquery(done_questions, output_field=IntegerField()), 0),
            correct_answers=Coalesce(Subquery(correct_answers, output_field=IntegerField()), 0),
        )
        .filter(
            Q(force_ended=True) | Q(done_questions__gte=F('length')),
            correct_answers__gte=SPECIES_PRACTICE_PASS_CORRECT,
        )
        .values_list('focus_species_id', flat=True)
    )
    return set(rows)


def get_confusion_pair_rows(country_code: str | None = None) -> list[dict[str, Any]]:
    """
    Undirected species pairs from incorrect answers, ordered by total wrong answers (desc).

    Directed columns: when the lower-ID species was the target vs when the higher-ID species was the target.

    If country_code is set, only pairs from games in that country are counted,
    and only where both species are on that country's checklist
    (CountrySpecies excludes introduced / uncertain / unknown).
    """
    cc = normalize_country_filter(country_code)
    pairs = (
        Answer.objects.filter(correct=False)
        .exclude(question__species_id=F("answer_id"))
        .exclude(question__species_id__isnull=True)
        .exclude(answer_id__isnull=True)
    )
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return []
        pairs = pairs.filter(
            question__game__country_id=cc,
            question__species_id__in=allowed,
            answer_id__in=allowed,
        )
    grouped = list(
        pairs.annotate(
            low_id=Least("question__species_id", "answer_id"),
            high_id=Greatest("question__species_id", "answer_id"),
        )
        .values("low_id", "high_id")
        .annotate(
            total_wrong=Count("id"),
            when_low_was_target=Count(
                "id", filter=Q(question__species_id__lt=F("answer_id"))
            ),
            when_high_was_target=Count(
                "id", filter=Q(question__species_id__gt=F("answer_id"))
            ),
        )
        .order_by("-total_wrong")
    )
    ids = {
        species_id
        for row in grouped
        for species_id in (row["low_id"], row["high_id"])
        if species_id is not None
    }
    species_map = Species.objects.in_bulk(ids)

    rows: list[dict[str, Any]] = []
    for row in grouped:
        low = species_map.get(row["low_id"])
        high = species_map.get(row["high_id"])
        rows.append(
            {
                "low_id": row["low_id"],
                "high_id": row["high_id"],
                "total_wrong": row["total_wrong"],
                "when_low_was_target": row["when_low_was_target"],
                "when_high_was_target": row["when_high_was_target"],
                "low_name": low.name if low else "",
                "high_name": high.name if high else "",
                "low_name_latin": low.name_latin if low else "",
                "high_name_latin": high.name_latin if high else "",
            }
        )
    return rows


def get_confused_partners_for_species(
    species_id: int,
    *,
    limit: int = 5,
    country_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    Other species most often mixed up with this one, in either direction.

    Counts incorrect answers where this species was the question target or the
    player's pick. Ordered by mix-up count descending.
    """
    if not species_id:
        return []

    cc = normalize_country_filter(country_code)
    pairs = (
        Answer.objects.filter(correct=False)
        .exclude(question__species_id=F("answer_id"))
        .filter(Q(question__species_id=species_id) | Q(answer_id=species_id))
    )
    if cc:
        allowed = _allowed_species_ids_for_country(cc)
        if not allowed:
            return []
        pairs = pairs.filter(
            question__game__country_id=cc,
            question__species_id__in=allowed,
            answer_id__in=allowed,
        )

    directed = list(
        pairs.values("question__species_id", "answer_id").annotate(c=Count("id"))
    )
    totals: dict[int, int] = defaultdict(int)
    for row in directed:
        target_id = row["question__species_id"]
        pick_id = row["answer_id"]
        other_id = pick_id if target_id == species_id else target_id
        if not other_id or other_id == species_id:
            continue
        totals[other_id] += row["c"]

    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[:limit]
    species_map = Species.objects.in_bulk([pk for pk, _ in ranked])
    rows: list[dict[str, Any]] = []
    for other_id, total_wrong in ranked:
        other = species_map.get(other_id)
        if other is None:
            continue
        rows.append(
            {
                "species_id": other_id,
                "name": other.name,
                "name_latin": other.name_latin or "",
                "slug": other.slug or "",
                "total_wrong": total_wrong,
            }
        )
    return rows


def render_species_mistakes_csv(species_rows: list[dict[str, Any]]) -> str:
    buf = StringIO()
    w = csv.writer(buf)

    w.writerow(["SPECIES MISTAKES"])
    w.writerow(
        [
            "species_id",
            "name",
            "name_latin",
            "times_shown",
            "correctly_answered",
            "wrongly_answered",
            "error_rate_pct",
        ]
    )
    for row in species_rows:
        w.writerow(
            [
                row["species_id"],
                row["name"],
                row["name_latin"],
                row["times_shown"],
                row["correctly_answered"],
                row["wrongly_answered"],
                f'{row["error_rate"]:.4f}' if row["error_rate"] is not None else "",
            ]
        )

    return buf.getvalue()


def render_pairs_mistakes_csv(pair_rows: list[dict[str, Any]]) -> str:
    buf = StringIO()
    w = csv.writer(buf)

    w.writerow(["CONFUSED PAIRS (undirected)"])
    w.writerow(
        [
            "species_low_id",
            "species_high_id",
            "low_name",
            "high_name",
            "total_wrong",
            "when_low_id_was_target",
            "when_high_id_was_target",
        ]
    )
    for row in pair_rows:
        w.writerow(
            [
                row["low_id"],
                row["high_id"],
                row["low_name"],
                row["high_name"],
                row["total_wrong"],
                row["when_low_was_target"],
                row["when_high_was_target"],
            ]
        )

    return buf.getvalue()


def _mistake_rows_cache_key(kind: str, country_code: str | None) -> str:
    return f"quiz-mistakes:{kind}:{(country_code or 'all').lower()}"


def cached_species_mistake_rows(country_code: str | None = None) -> list[dict[str, Any]]:
    cc = normalize_country_filter(country_code)
    key = _mistake_rows_cache_key("species", cc)
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows = get_species_mistake_rows(cc)
    cache.set(key, rows, MISTAKE_STATS_CACHE_TTL)
    return rows


def cached_confusion_pair_rows(country_code: str | None = None) -> list[dict[str, Any]]:
    cc = normalize_country_filter(country_code)
    key = _mistake_rows_cache_key("pairs", cc)
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows = get_confusion_pair_rows(cc)
    cache.set(key, rows, MISTAKE_STATS_CACHE_TTL)
    return rows


def quiz_mistakes_species_csv_response(request: HttpRequest) -> HttpResponse:
    species_sort = request.GET.get("species_sort", "error_rate")
    if species_sort not in ("error_rate", "times_shown"):
        species_sort = "error_rate"
    country_code = normalize_country_filter(request.GET.get("country"))
    species_rows = sort_species_rows(cached_species_mistake_rows(country_code), species_sort)
    content = render_species_mistakes_csv(species_rows)
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    fname = "quiz-mistake-species"
    if country_code:
        fname += f"-{country_code.lower()}"
    resp["Content-Disposition"] = f'attachment; filename="{fname}.csv"'
    return resp


def quiz_mistakes_pairs_csv_response(request: HttpRequest) -> HttpResponse:
    country_code = normalize_country_filter(request.GET.get("country"))
    pair_rows = cached_confusion_pair_rows(country_code)
    content = render_pairs_mistakes_csv(pair_rows)
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    fname = "quiz-mistake-pairs"
    if country_code:
        fname += f"-{country_code.lower()}"
    resp["Content-Disposition"] = f'attachment; filename="{fname}.csv"'
    return resp
