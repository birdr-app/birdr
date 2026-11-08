"""What the apps get from a trip's JSON files, and the player's progress.

``trip_payload`` holds everything the screens show (texts in one language, photos as display URLs).
``known_species`` is the player's side: species answered right in any game, in any country.
``record_answers`` stores a unit quiz as a ``trip_prep`` game, so it counts everywhere else too.
"""

from __future__ import annotations

from functools import lru_cache

from jizz.courses.content import text
from jizz.trips.content import DATA_DIR, TRIPS, country_dir, read_json

QUIZ_PHOTOS = 8


class TripNotFound(Exception):
    pass


def trip_language(country: str, wanted: str | None) -> str:
    languages = TRIPS[country]['languages']
    wanted = (wanted or '').lower()[:2]
    return wanted if wanted in languages else languages[0]


@lru_cache(maxsize=None)
def _files(country: str) -> dict:
    folder = country_dir(country)
    units = read_json(folder / 'units.json')
    if not units:
        raise TripNotFound(country)
    codes = [c for g in units['groups'] for c in g['species']]
    return {
        'units': units,
        'texts': read_json(folder / 'texts.json', {}) or {},
        'media': (read_json(folder / 'media.json', {}) or {}).get('species', {}),
        'scope': read_json(folder / 'scope.json', {}) or {},
        'groups': {g['slug']: read_json(DATA_DIR / 'groups' / f'{g["slug"]}.json', {}) or {} for g in units['groups']},
        'species': {c: read_json(DATA_DIR / 'species' / f'{c}.json', {}) or {} for c in codes},
    }


def _media_rows(ids) -> dict[int, dict]:
    from media.display_urls import media_object_display_url
    from media.models import Media

    rows = {}
    for media in Media.objects.filter(id__in=ids, hide=False):
        rows[media.id] = {
            'id': media.id,
            'url': media_object_display_url(media),
            'contributor': media.contributor,
            'license': media.copyright_standardized,
            'source': media.source,
        }
    return rows


def trip_summary(country: str, lang: str) -> dict:
    files = _files(country)
    units = files['units']
    endemics = [c for g in units['groups'] for c in g.get('endemics', [])]
    meta = TRIPS[country]
    return {
        'country': country,
        'name': text(meta['name'], lang),
        'species_count': sum(len(g['species']) for g in units['groups']),
        'endemic_count': len(endemics),
        'group_count': len(units['groups']),
        'languages': list(meta['languages']),
    }


def trip_payload(country: str, lang: str) -> dict:
    files = _files(country)
    units, texts = files['units'], files['texts']
    codes = [c for g in units['groups'] for c in g['species']]
    endemic_codes = {c for g in units['groups'] for c in g.get('endemics', [])}

    picks = {}
    for code in codes:
        entry = files['media'].get(code, {})
        picks[code] = (entry.get('card', []), entry.get('quiz', [])[:QUIZ_PHOTOS])
    rows = _media_rows({m for card, quiz in picks.values() for m in card + quiz})
    group_of = {c: g['slug'] for g in units['groups'] for c in g['species']}

    species = {}
    for code in codes:
        shared = files['species'][code]
        card, quiz = picks[code]
        species[code] = {
            'code': code,
            'species_id': files['media'].get(code, {}).get('species_id'),
            'name': text(shared.get('name'), lang),
            'latin': shared.get('latin', ''),
            'group': group_of[code],
            'endemic': code in endemic_codes,
            'look_for': [text(line, lang) for line in shared.get('look_for', [])],
            'here': text(texts.get('species', {}).get(code, {}).get('here'), lang),
            'images': [rows[m] for m in card if m in rows],
            'quiz_images': [rows[m] for m in quiz if m in rows],
        }

    groups = []
    for group in units['groups']:
        shared = files['groups'][group['slug']]
        groups.append({
            'slug': group['slug'],
            'name': text(group['name'], lang),
            'about': text(shared.get('about'), lang),
            'here': text(texts.get('groups', {}).get(group['slug'], {}).get('here'), lang),
            'false_friends': [
                {'if_known': f['if_known'], 'text': text(f['text'], lang)} for f in shared.get('false_friends', [])
            ],
            'species': group['species'],
            'endemics': group.get('endemics', []),
        })

    unit_texts = texts.get('units', {})
    endemic_texts = texts.get('endemics', {})
    first_day = texts.get('first_day', {})
    return {
        **trip_summary(country, lang),
        'lang': lang,
        'intro': text(texts.get('intro'), lang),
        'groups': groups,
        'units': [
            {
                'slug': u['slug'],
                'title': text(unit_texts.get(u['slug'], {}).get('title') or u['title'], lang),
                'intro': text(unit_texts.get(u['slug'], {}).get('intro'), lang),
                'groups': u['groups'],
                'species': u['species'],
            }
            for u in units['units']
        ],
        'first_day': {
            'slug': 'first-day',
            'title': text(first_day.get('title'), lang),
            'intro': text(first_day.get('intro'), lang),
            'groups': [],
            'species': units['first_day'],
        },
        'endemics': {
            'why_here': text(endemic_texts.get('why_here'), lang),
            'where': [
                {'title': text(w.get('title'), lang), 'text': text(w.get('text'), lang)}
                for w in endemic_texts.get('where', [])
            ],
            'families': [
                {'title': text(f.get('title'), lang), 'text': text(f.get('text'), lang)}
                for f in endemic_texts.get('families', [])
            ],
            'units': [
                {
                    'slug': u['slug'],
                    'title': text(endemic_texts.get('units', {}).get(u['slug'], {}).get('title'), lang),
                    'intro': '',
                    'groups': [],
                    'species': u['species'],
                }
                for u in units['endemic_units']
            ],
        },
        'species': species,
    }


# ---------------------------------------------------------------- the player's side


def players_for_request(request):
    """The players whose answers count: every player of a logged-in user, or the token's player."""
    from jizz.models import Player

    if request.user and request.user.is_authenticated:
        return list(Player.objects.filter(user=request.user))
    token = request.auth if isinstance(request.auth, str) else None
    if not token:
        return []
    return list(Player.objects.filter(token=token))


def known_species_ids(players) -> set[int]:
    """Species these players answered right at least once, in any game and any country."""
    from jizz.models import Answer

    if not players:
        return set()
    return set(
        Answer.objects.filter(player_score__player__in=players, correct=True)
        .values_list('question__species_id', flat=True)
        .distinct()
    )


def trip_progress(country: str, players) -> dict:
    files = _files(country)
    id_to_code = {entry.get('species_id'): code for code, entry in files['media'].items() if entry.get('species_id')}
    known = known_species_ids(players) & set(id_to_code)
    return {'country': country, 'known': sorted(id_to_code[i] for i in known), 'known_group_slugs': known_group_slugs(players)}


def known_group_slugs(players) -> list[str]:
    """Bird groups the players know a species of (any country): drives the false-friend notes."""
    from jizz.models import Species

    ids = known_species_ids(players)
    if not ids:
        return []
    return sorted(
        set(Species.objects.filter(id__in=ids, species_group__isnull=False).values_list('species_group__slug', flat=True))
    )


def record_answers(country: str, player, answers: list[dict]) -> int:
    """Store a finished unit quiz as a ``trip_prep`` game. ``answers`` holds species ids:
    ``{"species_id", "answer_id", "media_id"}``. Scores stay 0, so trip quizzes never reach a
    leaderboard. Returns the game id."""
    from django.db import transaction

    from jizz.models import Answer, Country, Game, PlayerScore, Question, Species

    files = _files(country)
    allowed = {entry.get('species_id') for entry in files['media'].values()}
    rows = [a for a in answers if a.get('species_id') in allowed and a.get('answer_id')]
    if not rows:
        return 0
    species = {s.id: s for s in Species.objects.filter(id__in={a['species_id'] for a in rows} | {a['answer_id'] for a in rows})}
    rows = [a for a in rows if a['species_id'] in species and a['answer_id'] in species]
    from media.models import Media

    media_ids = set(Media.objects.filter(id__in={a.get('media_id') for a in rows if a.get('media_id')}).values_list('id', flat=True))

    with transaction.atomic():
        game = Game.objects.create(
            country=Country.objects.filter(code=country).first(),
            language=player.language or 'en',
            level='beginner',
            length=len(rows),
            game_type=Game.GAME_TYPE_TRIP_PREP,
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game)
        for number, row in enumerate(rows, start=1):
            question = Question.objects.create(
                game=game,
                species=species[row['species_id']],
                number=number,
                sequence=number,
                done=True,
                media_id=row.get('media_id') if row.get('media_id') in media_ids else None,
            )
            Answer.objects.create(question=question, player_score=score, answer=species[row['answer_id']])
        Answer.objects.filter(player_score=score).update(score=0)
        PlayerScore.objects.filter(pk=score.pk).update(score=0)
    return game.id
