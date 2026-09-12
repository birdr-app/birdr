"""Club Mix flock challenge generation and immutable attempt cloning."""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from typing import Sequence

from django.db import transaction
from django.utils.text import slugify

from jizz.game_question_selection import (
    advanced_option_species,
    beginner_option_species,
    candidate_species_ids,
    media_type_for_game,
    pick_species_with_eligible_media,
    question_target_species_ids,
)
from jizz.models import (
    Game,
    Question,
)
from jizz.question_play import fetch_eligible_media_for_species
from media.models import Media

# Club Mix: difficulty ramps in fixed play order (never shuffled after snapshot).
# beginner+familiar → advanced+regular → advanced+exceptional. Photos only (no audio).
# The closing exceptional slot opens the full frequency tier, vagrants included
# (see Game.RARIT_FREQUENCY_TIERS); the two slots before it cannot surface one.
CLUB_MIX_SLOTS: list[tuple[str, str, str, int]] = [
    # (level, rarity, game_media, count) — sequence order = play order
    ('beginner', Game.RARIT_FAMILIAR, 'images', 5),
    ('advanced', Game.RARIT_REGULAR, 'images', 10),
    ('advanced', Game.RARIT_EXCEPTIONAL, 'images', 10),
]

CLUB_MIX_LENGTH = sum(slot[3] for slot in CLUB_MIX_SLOTS)
INVITE_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no I/O/0/1


class InsufficientChallengeContent(Exception):
    """Raised when the country checklist cannot fill the immutable Club Mix set."""

    def __init__(self, message: str, *, needed: int = 0, available: int = 0):
        super().__init__(message)
        self.needed = needed
        self.available = available


@dataclass
class SnapshotItem:
    sequence: int
    species_id: int
    media_id: int
    media_type: str
    level: str
    rarity: str
    option_species_ids: list[int]


def generate_invite_code(length: int = 6) -> str:
    return ''.join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(length))


def unique_flock_slug(name: str, *, exclude_pk=None) -> str:
    from jizz.models import Flock

    base = slugify(name)[:40] or 'flock'
    slug = base
    n = 2
    while True:
        qs = Flock.objects.filter(slug=slug)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        slug = f'{base}-{n}'[:50]
        n += 1


def _scratch_game(*, country, level: str, rarity: str, media: str, host) -> Game:
    return Game(
        country=country,
        level=level,
        length=CLUB_MIX_LENGTH,
        media=media,
        rarity=rarity,
        include_escapes=False,
        multiplayer=False,
        host=host,
        game_type=Game.GAME_TYPE_STANDARD,
        language='en',
    )


def _build_slot_items(
    *,
    country,
    host,
    level: str,
    rarity: str,
    media: str,
    count: int,
    used_species_ids: set[int],
    start_sequence: int,
) -> list[SnapshotItem]:
    scratch = _scratch_game(
        country=country, level=level, rarity=rarity, media=media, host=host
    )
    option_ids = candidate_species_ids(scratch)
    target_ids = [
        sid for sid in question_target_species_ids(scratch, option_ids)
        if sid not in used_species_ids
    ]
    if len(target_ids) < count:
        raise InsufficientChallengeContent(
            f'Not enough species for {level}/{rarity}/{media} '
            f'(need {count}, found {len(target_ids)}).',
            needed=count,
            available=len(target_ids),
        )

    media_type = media_type_for_game(scratch)
    items: list[SnapshotItem] = []
    local_used = set(used_species_ids)

    for i in range(count):
        pool = [sid for sid in target_ids if sid not in local_used]
        if not pool:
            raise InsufficientChallengeContent(
                f'Ran out of unique species for {level}/{media}.',
                needed=count,
                available=len(items),
            )
        species, _number = pick_species_with_eligible_media(scratch, pool, local_used)
        local_used.add(species.id)

        if level == 'beginner':
            options = beginner_option_species(option_ids, species)
        else:
            options = advanced_option_species(option_ids, species)
        # beginner/advanced helpers append the answer last; shuffle like live games.
        option_ids_ordered = [s.id for s in options]
        if species.id not in option_ids_ordered:
            option_ids_ordered.append(species.id)
        random.shuffle(option_ids_ordered)

        eligible = fetch_eligible_media_for_species(species.id, media_type)
        if not eligible:
            raise InsufficientChallengeContent(
                f'No eligible {media_type} media for species {species.id}.',
            )
        media_obj = random.choice(eligible)

        items.append(
            SnapshotItem(
                sequence=start_sequence + i,
                species_id=species.id,
                media_id=media_obj.id,
                media_type=media_type,
                level=level,
                rarity=rarity,
                option_species_ids=option_ids_ordered,
            )
        )

    return items


def generate_club_mix_snapshot(*, country, host) -> list[SnapshotItem]:
    """Build the immutable Club Mix question set or raise InsufficientChallengeContent."""
    used: set[int] = set()
    items: list[SnapshotItem] = []
    seq = 1
    for level, rarity, media, count in CLUB_MIX_SLOTS:
        slot_items = _build_slot_items(
            country=country,
            host=host,
            level=level,
            rarity=rarity,
            media=media,
            count=count,
            used_species_ids=used,
            start_sequence=seq,
        )
        for item in slot_items:
            used.add(item.species_id)
        items.extend(slot_items)
        seq += count
    if len(items) != CLUB_MIX_LENGTH:
        raise InsufficientChallengeContent(
            f'Expected {CLUB_MIX_LENGTH} questions, built {len(items)}.',
            needed=CLUB_MIX_LENGTH,
            available=len(items),
        )
    return items


@transaction.atomic
def persist_challenge_snapshot(challenge, snapshot: Sequence[SnapshotItem]) -> None:
    from jizz.models import FlockChallengeItem

    FlockChallengeItem.objects.filter(challenge=challenge).delete()
    FlockChallengeItem.objects.bulk_create(
        [
            FlockChallengeItem(
                challenge=challenge,
                sequence=item.sequence,
                species_id=item.species_id,
                media_id=item.media_id,
                media_type=item.media_type,
                level=item.level,
                rarity=item.rarity,
                option_species_ids=item.option_species_ids,
            )
            for item in snapshot
        ]
    )


@transaction.atomic
def clone_challenge_into_game(*, challenge, host, language: str = 'en') -> Game:
    """Create a per-attempt Game preserving snapshot sequence (easy → hard)."""
    from jizz.models import FlockChallengeItem
    from jizz.pregenerated_game import PregeneratedItem, fill_pregenerated_game

    items = list(
        FlockChallengeItem.objects.filter(challenge=challenge).order_by('sequence')
    )
    if len(items) != challenge.length:
        raise InsufficientChallengeContent(
            'Challenge snapshot is incomplete; refuse to start unequal attempts.',
            needed=challenge.length,
            available=len(items),
        )

    game = Game.objects.create(
        country=challenge.country,
        level='advanced',
        length=challenge.length,
        media='images',
        rarity=Game.RARIT_REGULAR,
        include_escapes=False,
        multiplayer=False,
        host=host,
        language=language or 'en',
        game_type=Game.GAME_TYPE_FLOCK_CHALLENGE,
        questions_pregenerated=True,
    )

    pregenerated: list[PregeneratedItem] = []
    for item in items:
        option_ids = list(item.option_species_ids or [])
        # Re-shuffle per attempt so older snapshots (answer last) are not biased,
        # and players don't all see the same button order.
        random.shuffle(option_ids)
        pregenerated.append(
            PregeneratedItem(
                sequence=item.sequence,
                species_id=item.species_id,
                media_id=item.media_id,
                option_species_ids=option_ids,
            )
        )
    fill_pregenerated_game(game, pregenerated)

    return game


def link_attempt_questions(attempt, game: Game) -> None:
    """Attach snapshot media locks for each question on the attempt game."""
    from jizz.models import FlockChallengeAttemptQuestion, FlockChallengeItem

    items_by_species_media = {
        (item.species_id, item.media_id): item
        for item in FlockChallengeItem.objects.filter(challenge=attempt.challenge)
    }
    # Match by species; media is unique per species within a challenge.
    items_by_species = {
        item.species_id: item
        for item in FlockChallengeItem.objects.filter(challenge=attempt.challenge)
    }
    rows = []
    for question in game.questions.all():
        item = items_by_species.get(question.species_id)
        if item is None:
            continue
        rows.append(
            FlockChallengeAttemptQuestion(
                attempt=attempt,
                challenge_item=item,
                question=question,
            )
        )
    FlockChallengeAttemptQuestion.objects.bulk_create(rows)


def locked_media_for_question(question: Question) -> Media | None:
    """Prefer Question.media; fall back to flock attempt link for older attempts."""
    if question.media_id:
        return question.media

    from jizz.models import FlockChallengeAttemptQuestion

    link = (
        FlockChallengeAttemptQuestion.objects.select_related('challenge_item__media')
        .filter(question_id=question.id)
        .first()
    )
    if link and link.challenge_item_id:
        return link.challenge_item.media
    return None


def flock_content_fingerprint(challenge) -> set[tuple]:
    """Species + media + frozenset(options) — order-independent identity of the set."""
    from jizz.models import FlockChallengeItem

    return {
        (
            item.species_id,
            item.media_id,
            frozenset(item.option_species_ids or []),
        )
        for item in FlockChallengeItem.objects.filter(challenge=challenge)
    }
