"""
Play-mode question loading: prefetch + lean JSON (one media item, light options).
"""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Prefetch

from jizz.models import Game, Question, QuestionOption, SpeciesName
from jizz.serializers import QuestionPlaySerializer
from media.models import Media, MediaReview


def rotate_media_list_for_play(items: list[Media], active_index: int) -> list[Media]:
    """
    Return eligible media with the active item first.

    Play JSON only ships the current clip; index 0 is that item so older clients
    that only read ``images[0]`` stay correct. Flagging uses ``/next-media/``.
    """
    if not items:
        return []
    idx = min(max(active_index, 0), len(items) - 1)
    if idx == 0:
        return items
    return items[idx:] + items[:idx]


def active_play_media(items: list[Media], active_index: int) -> list[Media]:
    """The single media item currently shown in play (after rotation)."""
    rotated = rotate_media_list_for_play(items, active_index)
    return rotated[:1] if rotated else []


def _eligible_media_list(media_rows: list[Media]) -> list[Media]:
    """Same rules as Species._eligible_media, in Python after prefetch reviews."""
    if not media_rows:
        return []
    approved = []
    fallback = []
    for m in media_rows:
        reviews = list(m.reviews.all())
        if not reviews:
            fallback.append(m)
            continue
        latest = max(reviews, key=lambda r: r.id)
        if latest.review_type == MediaReview.APPROVED:
            approved.append(m)
        elif latest.review_type != MediaReview.REJECTED:
            fallback.append(m)
    if approved:
        return sorted(approved, key=lambda m: m.id)
    return sorted(fallback, key=lambda m: m.id)


def fetch_eligible_media_for_species(species_id: int, media_type: str) -> list[Media]:
    rows = list(
        Media.objects.filter(
            species_id=species_id,
            type=media_type,
            hide=False,
        )
        .prefetch_related('reviews')
        .order_by('id')
    )
    return _eligible_media_list(rows)


def prefetch_eligible_media_by_species(
    species_ids: list[int],
    media_type: str,
) -> dict[int, list[Media]]:
    if not species_ids:
        return {}
    rows = list(
        Media.objects.filter(
            species_id__in=species_ids,
            type=media_type,
            hide=False,
        )
        .prefetch_related('reviews')
        .order_by('id')
    )
    by_species: dict[int, list[Media]] = defaultdict(list)
    for row in rows:
        by_species[row.species_id].append(row)
    return {
        sid: _eligible_media_list(items)
        for sid, items in by_species.items()
    }


def load_question_for_play(question_id: int) -> Question:
    return (
        Question.objects.select_related('game', 'game__country', 'species', 'media')
        .prefetch_related(
            Prefetch(
                'options',
                queryset=QuestionOption.objects.select_related('species').order_by(
                    'order'
                ),
            ),
        )
        .get(pk=question_id)
    )


def build_play_serializer_context(question: Question) -> dict:
    game = question.game
    media_type = {'images': 'image', 'video': 'video', 'audio': 'audio'}.get(
        game.media, 'image'
    )
    species_ids = [question.species_id]
    species_ids.extend(opt.species_id for opt in question.options.all())

    locked_media = None
    if question.media_id:
        locked_media = question.media
    elif game.game_type == Game.GAME_TYPE_FLOCK_CHALLENGE or game.questions_pregenerated:
        from jizz.flock_challenge import locked_media_for_question

        locked_media = locked_media_for_question(question)

    if locked_media is not None:
        media_type = locked_media.type

    # Play UI only shows media for the answer species; options are names only.
    if locked_media is not None:
        media_by_species = {question.species_id: [locked_media]}
    else:
        full = prefetch_eligible_media_by_species(
            [question.species_id], media_type
        )
        media_by_species = {
            sid: active_play_media(items, question.number or 0)
            for sid, items in full.items()
        }

    lang = game.language
    names: dict[tuple[int, str], str] = {}
    if lang:
        if str(lang).lower().split('-')[0].split('_')[0] == 'la':
            by_id = {}
            if question.species_id and getattr(question, 'species', None):
                by_id[question.species_id] = question.species
            for opt in question.options.all():
                if opt.species_id and opt.species:
                    by_id[opt.species_id] = opt.species
            for sid, species in by_id.items():
                names[(sid, lang)] = species.name_latin or species.name
        else:
            for sn in SpeciesName.objects.filter(
                species_id__in=species_ids, language_id=lang
            ):
                names[(sn.species_id, lang)] = sn.name

    return {
        'play_mode': True,
        'game': game,
        'play_media_type': media_type,
        'play_media_by_species': media_by_species,
        'play_species_names': names,
        'play_language': lang,
    }


def serialize_question_for_play(question: Question) -> dict:
    """Serialize after ``load_question_for_play`` or with options prefetched."""
    ctx = build_play_serializer_context(question)
    return QuestionPlaySerializer(question, context=ctx).data


def advance_question_media_after_exclusion(
    question: Question,
    excluded_media_id: int | None = None,
) -> Question | None:
    """
    After a player flags/rejects the current media, point ``question.number`` at the
    next eligible item (refreshed list — rejected media is excluded).
    """
    game = question.game
    media_type = {'images': 'image', 'video': 'video', 'audio': 'audio'}.get(
        game.media, 'image'
    )
    # Mixed-media games (flock Club Mix) lock type on the question itself.
    if question.media_id and question.media is not None:
        media_type = question.media.type
    full_eligible = fetch_eligible_media_for_species(question.species_id, media_type)
    if not full_eligible:
        return None

    remaining = full_eligible
    if excluded_media_id:
        remaining = [m for m in full_eligible if m.id != excluded_media_id]
    if not remaining:
        return None

    if len(remaining) == 1:
        question.number = full_eligible.index(remaining[0])
        question.save(update_fields=['number'])
        return question

    current_idx = min(max(question.number or 0, 0), len(full_eligible) - 1)
    current_media = full_eligible[current_idx]

    if excluded_media_id and current_media.id == excluded_media_id:
        next_media = remaining[0]
    else:
        try:
            pos_in_remaining = remaining.index(current_media)
            next_media = remaining[(pos_in_remaining + 1) % len(remaining)]
        except ValueError:
            next_media = remaining[0]

    question.number = full_eligible.index(next_media)
    question.save(update_fields=['number'])
    return question
