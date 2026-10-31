"""Shared games: one frozen question set, played by everyone with the link on their own time."""

from __future__ import annotations

import random
from datetime import timedelta

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from jizz.game_question_selection import create_question_for_game, media_type_for_game
from jizz.models import Answer, FlockSharedGame, Game, Player, SharedGame, SharedGameAttempt, Species
from jizz.pregenerated_game import PregeneratedItem, fill_pregenerated_game
from jizz.question_play import active_play_media, fetch_eligible_media_for_species
from media.display_urls import media_object_display_url

SHAREABLE_GAME_TYPES = (Game.GAME_TYPE_STANDARD, Game.GAME_TYPE_EXTREME)
MAX_LENGTH = 100
MAX_DURATION_HOURS = SharedGame.MAX_OPEN_DAYS * 24
LEADERBOARD_SIZE = 50
WRONG_ANSWERS_PER_QUESTION = 3

# Settings copied from the template onto every attempt game.
_CLONED_FIELDS = (
    'country', 'level', 'length', 'media', 'repeat', 'rarity', 'include_escapes',
    'difficult_species', 'game_type', 'speed_seconds', 'tax_family', 'tax_order',
    'species_group', 'season',
)


class SharedGameContentError(Exception):
    """The chosen settings cannot fill the whole question set."""


@transaction.atomic
def build_template_questions(game: Game) -> None:
    """Create every question up front and lock the media each player will see."""
    media_type = media_type_for_game(game)
    for _ in range(game.length):
        try:
            question = create_question_for_game(game)
        except ValueError as exc:
            raise SharedGameContentError(str(exc)) from exc
        shown = active_play_media(
            fetch_eligible_media_for_species(question.species_id, media_type),
            question.number or 0,
        )
        if not shown:
            raise SharedGameContentError(f'No {media_type} media for species {question.species_id}.')
        question.media = shown[0]
        question.save(update_fields=['media'])
    # The template itself is never played.
    game.questions_pregenerated = True
    game.force_ended = True
    game.save(update_fields=['questions_pregenerated', 'force_ended'])


def create_shared_game(*, owner, template: Game, duration_hours: int | None) -> SharedGame:
    build_template_questions(template)
    ends_at = timezone.now() + timedelta(hours=duration_hours) if duration_hours else None
    return SharedGame.objects.create(owner=owner, template_game=template, ends_at=ends_at)


@transaction.atomic
def clone_attempt_game(shared_game: SharedGame, player: Player) -> Game:
    """A fresh Game for one player with the template's questions, media and options."""
    template = shared_game.template_game
    game = Game.objects.create(
        **{field: getattr(template, field) for field in _CLONED_FIELDS},
        language=player.language or template.language,
        multiplayer=False,
        host=player,
        questions_pregenerated=True,
    )
    items = []
    for question in template.questions.order_by('sequence').prefetch_related('questionoption_set'):
        option_ids = [opt.species_id for opt in question.questionoption_set.all()]
        # Same options for everyone, but not the same button order.
        random.shuffle(option_ids)
        items.append(
            PregeneratedItem(
                sequence=question.sequence,
                species_id=question.species_id,
                media_id=question.media_id,
                option_species_ids=option_ids,
            )
        )
    fill_pregenerated_game(game, items)
    return game


def attempt_for(shared_game: SharedGame, player: Player) -> SharedGameAttempt | None:
    """The attempt of this person: by account when logged in, else by guest player."""
    attempts = SharedGameAttempt.objects.select_related('game', 'player')
    if player.user_id:
        found = attempts.filter(shared_game=shared_game, user_id=player.user_id).first()
        if found:
            return found
    return attempts.filter(shared_game=shared_game, player=player).first()


def start_attempt(shared_game: SharedGame, player: Player) -> tuple[SharedGameAttempt, bool]:
    """Return (attempt, created); resumes an unfinished attempt instead of starting another."""
    existing = attempt_for(shared_game, player)
    if existing:
        return existing, False
    with transaction.atomic():
        game = clone_attempt_game(shared_game, player)
        attempt = SharedGameAttempt.objects.create(
            shared_game=shared_game,
            player=player,
            user_id=player.user_id,
            game=game,
        )
    return attempt, True


def leaderboard(shared_game: SharedGame, player: Player | None = None) -> dict:
    rows = list(
        SharedGameAttempt.objects.filter(shared_game=shared_game, is_ranked=True)
        .select_related('player')
        .order_by('-score', '-correct_count', 'completed_at', 'id')
    )
    mine = attempt_for(shared_game, player) if player else None
    length = shared_game.template_game.length
    entries = [
        {
            'rank': rank,
            'name': attempt.player.name or 'Player',
            'score': attempt.score,
            'correct_count': attempt.correct_count,
            'length': length,
            'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
            'is_me': mine is not None and attempt.pk == mine.pk,
        }
        for rank, attempt in enumerate(rows, start=1)
    ]
    me = next((entry for entry in entries if entry['is_me']), None)
    top = entries[:LEADERBOARD_SIZE]
    if me and me not in top:
        top.append(me)
    return {'entries': top, 'total_participants': len(entries), 'me': me}


def question_stats(shared_game: SharedGame, language: str = 'en') -> list[dict]:
    """Per question: how many ranked players got it right, and the most common wrong answers."""
    from jizz.services.checklist import localized_species_names, normalize_species_language

    template_questions = list(
        shared_game.template_game.questions.order_by('sequence').select_related('media')
    )
    answers = (
        Answer.objects.filter(
            question__game__shared_attempt__shared_game=shared_game,
            question__game__shared_attempt__is_ranked=True,
        )
        .values('question__sequence', 'answer_id', 'correct')
        .annotate(n=Count('id'))
    )
    totals: dict[int, dict] = {}
    for row in answers:
        bucket = totals.setdefault(row['question__sequence'], {'answered': 0, 'correct': 0, 'wrong': {}})
        bucket['answered'] += row['n']
        if row['correct']:
            bucket['correct'] += row['n']
        else:
            bucket['wrong'][row['answer_id']] = bucket['wrong'].get(row['answer_id'], 0) + row['n']

    species_ids = {q.species_id for q in template_questions}
    for bucket in totals.values():
        species_ids.update(bucket['wrong'])
    species_by_id = Species.objects.in_bulk(species_ids)
    names = localized_species_names(species_by_id, normalize_species_language(language))

    def name(species_id):
        species = species_by_id.get(species_id)
        return names.get(species_id) or (species.name if species else '')

    stats = []
    for question in template_questions:
        bucket = totals.get(question.sequence, {'answered': 0, 'correct': 0, 'wrong': {}})
        wrong = sorted(bucket['wrong'].items(), key=lambda kv: (-kv[1], kv[0]))
        species = species_by_id.get(question.species_id)
        stats.append(
            {
                'sequence': question.sequence,
                'species': {
                    'id': question.species_id,
                    'name': name(question.species_id),
                    'name_latin': species.name_latin if species else '',
                    'code': (species.code or '') if species else '',
                },
                'media': {
                    'type': question.media.type,
                    'url': media_object_display_url(question.media),
                    'contributor': question.media.contributor,
                } if question.media_id else None,
                'answered': bucket['answered'],
                'correct': bucket['correct'],
                'wrong_answers': [
                    {'species_id': sid, 'name': name(sid), 'count': count}
                    for sid, count in wrong[:WRONG_ANSWERS_PER_QUESTION]
                ],
            }
        )
    return stats


MEDIA_PREVIEW_LABELS = {'images': 'pictures', 'audio': 'sounds', 'video': 'videos'}


def share_preview(shared_game: SharedGame) -> dict:
    """English title + description for chat link previews (WhatsApp, Signal, …)."""
    from jizz.user_names import player_name_for_user

    template = shared_game.template_game
    owner = player_name_for_user(shared_game.owner)
    country = template.country.name if template.country else 'Motmot'
    media = MEDIA_PREVIEW_LABELS.get(template.media, template.media)
    played = SharedGameAttempt.objects.filter(shared_game=shared_game, is_ranked=True).count()
    parts = [f'{template.length} {media}', template.level.title()]
    if played:
        parts.append(f'{played} played')
    if not shared_game.is_open:
        parts.append('finished')
    return {
        'title': f'{owner} shared a Motmot quiz: {country}',
        'description': ' · '.join(parts) + '. Can you beat the others?',
    }


FLOCK_PUSH_MESSAGES = {
    'en': {
        'title': 'Motmot: {flock}',
        'body': '{name} shared a new game: {country}, {length} birds. Tap to play!',
    },
    'nl': {
        'title': 'Motmot: {flock}',
        'body': '{name} heeft een nieuw spel gedeeld: {country}, {length} vogels. Tik om te spelen!',
    },
}


def add_to_flock(shared_game: SharedGame, flock, user) -> tuple[FlockSharedGame, bool]:
    """Post a shared game to a flock's Extra games; on first add, push the other members."""

    link, created = FlockSharedGame.objects.get_or_create(
        flock=flock, shared_game=shared_game, defaults={'added_by': user}
    )
    if created:
        notify_flock_of_shared_game(link)
    return link, created


def notify_flock_of_shared_game(link) -> int:
    """Push members (notifications on, not the one who shared it) about a new extra game."""
    from jizz.flock_schedule import _lang
    from jizz.models import FlockMembership
    from jizz.notifications import send_push_to_user
    from jizz.user_names import player_name_for_user

    flock = link.flock
    template = link.shared_game.template_game
    name = player_name_for_user(link.added_by) if link.added_by else 'A member'
    data = {'type': 'shared_game', 'token': link.shared_game.token, 'flock_slug': flock.slug}
    memberships = (
        FlockMembership.objects.filter(flock=flock, notifications_enabled=True)
        .exclude(user_id=link.added_by_id)
        .select_related('user', 'user__profile')
    )
    sent = 0
    for membership in memberships:
        msg = FLOCK_PUSH_MESSAGES[_lang(membership.user)]
        try:
            send_push_to_user(
                membership.user,
                msg['title'].format(flock=flock.name),
                msg['body'].format(
                    name=name,
                    country=template.country.name if template.country else 'Motmot',
                    length=template.length,
                ),
                data=data,
            )
            sent += 1
        except Exception:
            pass
    return sent
