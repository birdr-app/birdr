"""Load course lessons from JSON and turn them into what the apps show.

A lesson file holds texts per language (``{"nl": ..., "en": ...}``), species ids and the media
ids picked for each bird. ``lesson_payload`` returns the texts in one language and the media as
display URLs, plus the birds of earlier lessons the quiz may repeat.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from media.display_urls import media_object_display_url

DATA_DIR = Path(__file__).resolve().parent / 'data'

# Courses the apps can open: slug -> title and the language its texts are written in.
COURSES = {
    'nl-beginners': {
        'title': {'nl': 'Vogels van Nederland', 'en': 'Birds of the Netherlands'},
        'subtitle': {
            'nl': 'Een cursus voor beginners: elke week een korte les',
            'en': 'A course for beginners: one short lesson a week',
        },
        'languages': ('nl',),
    },
}


class LessonNotFound(Exception):
    pass


@lru_cache(maxsize=None)
def course_lessons(slug: str) -> tuple[dict, ...]:
    """All lessons of a course, ordered by week."""
    if slug not in COURSES:
        raise LessonNotFound(slug)
    folder = DATA_DIR / slug
    lessons = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('lesson-*.json'))]
    return tuple(sorted(lessons, key=lambda lesson: lesson['week']))


@lru_cache(maxsize=None)
def lookalike_groups(slug: str) -> tuple[tuple[int, ...], ...]:
    """Groups of species that beginners mix up (data/<course>/lookalikes.json)."""
    path = DATA_DIR / slug / 'lookalikes.json'
    if not path.exists():
        return ()
    groups = json.loads(path.read_text(encoding='utf-8')).get('groups', [])
    return tuple(tuple(g['ids']) for g in groups)


def lesson_by_week(slug: str, week: int) -> dict:
    for lesson in course_lessons(slug):
        if lesson['week'] == week:
            return lesson
    raise LessonNotFound(f'{slug} week {week}')


def photo_picks(slug: str) -> dict[tuple[int, int], dict]:
    """Photos chosen by admins, keyed by (week, species_id)."""
    from jizz.models import CoursePhotoPick

    return {
        (p.week, p.species_id): {'card': p.card, 'quiz': p.quiz, 'reject': p.reject, 'done': p.done}
        for p in CoursePhotoPick.objects.filter(course=slug)
    }


def effective_lessons(slug: str) -> list[dict]:
    """The lessons with admin-chosen photos in place of the ones in the files.

    A bird with no main photo yet (marked `needs_photos` in its file until one is chosen) is left
    out, so the apps never show an empty card.
    """
    picks = photo_picks(slug)
    lessons = []
    media_by_bird = {}  # (week, species_id) -> media, for birds that reuse an earlier lesson's photos
    for lesson in course_lessons(slug):
        lesson = copy.deepcopy(lesson)
        for bird in lesson.get('birds', []):
            # A bird repeated in the same plumage (the song lesson) shows the photos chosen for it
            # in the lesson where it was taught, so they are picked only once.
            source = bird.get('photos_from_week')
            if source and (source, bird['species_id']) in media_by_bird:
                bird['media'] = copy.deepcopy(media_by_bird[(source, bird['species_id'])])
            else:
                pick = picks.get((lesson['week'], bird['species_id']))
                if pick and (pick['card'] or pick['quiz']):
                    bird['media'] = {'card': list(pick['card']), 'quiz': list(pick['quiz'])}
            media_by_bird[(lesson['week'], bird['species_id'])] = bird['media']
        lesson['birds'] = [b for b in lesson.get('birds', []) if b['media']['card']]
        lessons.append(lesson)
    return lessons


def clear_cache(slug: str) -> None:
    """Forget the cached course and lesson payloads, e.g. after photos were changed."""
    from django.core.cache import cache

    keys = []
    for lang in COURSES[slug]['languages']:
        keys.append(f'course:{slug}:{lang}')
        keys.extend(f'course:{slug}:{lesson["week"]}:{lang}' for lesson in course_lessons(slug))
    cache.delete_many(keys)


def text(value, lang: str) -> str:
    """One language from a ``{"nl": ..., "en": ...}`` object; plain strings pass through."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    return value.get(lang) or value.get('nl') or value.get('en') or ''


def _media_ids(lessons) -> set[int]:
    ids: set[int] = set()
    for lesson in lessons:
        for bird in lesson.get('birds', []):
            media = bird.get('media', {})
            ids.update(media.get('card', []))
            ids.update(media.get('quiz', []))
            ids.update(s['media_id'] for s in bird.get('sound', {}).get('chosen', []))
    return ids


def _media_rows(ids) -> dict[int, dict]:
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


def _pick(ids, rows) -> list[dict]:
    return [rows[i] for i in ids if i in rows]


def _bird(bird: dict, rows: dict, lang: str) -> dict:
    media = bird.get('media', {})
    sound = bird.get('sound', {})
    return {
        'species_id': bird['species_id'],
        'name': text(bird['name'], lang),
        'latin': bird.get('latin', ''),
        'plumage': text(bird.get('plumage'), lang),
        'look_for': [text(line, lang) for line in bird.get('look_for', [])],
        'where_when': text(bird.get('where_when'), lang),
        'note': text(bird.get('note'), lang),
        'dont_confuse': text(bird.get('dont_confuse'), lang),
        'sound': {
            'type': sound.get('type', ''),
            'describe': text(sound.get('describe'), lang),
        },
        'images': _pick(media.get('card', []), rows),
        'quiz_images': _pick(media.get('quiz', []), rows),
        'sounds': _pick([s['media_id'] for s in sound.get('chosen', [])], rows),
    }


def lesson_payload(slug: str, week: int, lang: str = 'nl') -> dict:
    lesson_by_week(slug, week)  # raises LessonNotFound
    lessons = effective_lessons(slug)
    lesson = next(l for l in lessons if l['week'] == week)
    weeks = set(lesson.get('quiz', {}).get('review_from') or [])
    review_lessons = [other for other in lessons if other['week'] in weeks]
    rows = _media_rows(_media_ids([lesson, *review_lessons]))

    review_birds = []
    seen = {(b['species_id'], text(b.get('plumage'), lang)) for b in lesson.get('birds', [])}
    for other in review_lessons:
        for bird in other.get('birds', []):
            key = (bird['species_id'], text(bird.get('plumage'), lang))
            if key in seen:
                continue
            seen.add(key)
            full = _bird(bird, rows, lang)
            review_birds.append({
                'species_id': full['species_id'],
                'name': full['name'],
                'plumage': full['plumage'],
                'from_week': other['week'],
                'quiz_images': full['quiz_images'] or full['images'],
                'sounds': full['sounds'],
            })

    # Every bird taught up to and including this lesson: the quiz takes its wrong answers from
    # these, look-alikes of the right answer first.
    known = {}
    for other in lessons:
        if other['week'] <= week:
            for bird in other.get('birds', []):
                known.setdefault(bird['species_id'], text(bird['name'], lang))
    lookalikes = [
        [sid for sid in group if sid in known]
        for group in lookalike_groups(slug)
    ]

    compare = lesson.get('compare')
    quiz = lesson.get('quiz', {})
    return {
        'course': slug,
        'week': lesson['week'],
        'slug': lesson['slug'],
        'kind': lesson.get('kind', 'species'),
        'season': lesson.get('season', 'any'),
        'minutes': lesson.get('minutes', 10),
        'title': text(lesson['title'], lang),
        'subtitle': text(lesson.get('subtitle'), lang),
        'intro': text(lesson.get('intro'), lang),
        'words': [
            {'term': text(w['term'], lang), 'explain': text(w['explain'], lang)}
            for w in lesson.get('words', [])
        ],
        'birds': [_bird(b, rows, lang) for b in lesson.get('birds', [])],
        'compare': {
            'after_species_id': compare.get('after_species_id'),
            'species_ids': compare.get('species_ids', []),
            'title': text(compare.get('title'), lang),
            'text': text(compare.get('text'), lang),
        } if compare else None,
        'quiz': {
            'questions': quiz.get('questions', 8),
            'kind': quiz.get('kind', 'photo'),
            'review_questions': quiz.get('review_questions', 0),
        },
        'review_birds': review_birds,
        'known_species': [{'species_id': sid, 'name': name} for sid, name in known.items()],
        'lookalikes': [group for group in lookalikes if len(group) > 1],
        'outside': text(lesson.get('outside'), lang),
        'next': text(lesson.get('next'), lang),
    }


def course_payload(slug: str, lang: str = 'nl') -> dict:
    meta = COURSES[slug]
    lessons = effective_lessons(slug)
    first_card = {}
    for lesson in lessons:
        birds = lesson.get('birds', [])
        if birds and birds[0].get('media', {}).get('card'):
            first_card[lesson['week']] = birds[0]['media']['card'][0]
    rows = _media_rows(first_card.values())
    return {
        'slug': slug,
        'title': text(meta['title'], lang),
        'subtitle': text(meta['subtitle'], lang),
        'languages': list(meta['languages']),
        'lessons': [
            {
                'week': lesson['week'],
                'slug': lesson['slug'],
                'kind': lesson.get('kind', 'species'),
                'title': text(lesson['title'], lang),
                'subtitle': text(lesson.get('subtitle'), lang),
                'minutes': lesson.get('minutes', 10),
                'bird_count': len(lesson.get('birds', [])),
                'image': rows.get(first_card.get(lesson['week']), {}).get('url'),
            }
            for lesson in lessons
        ],
    }
