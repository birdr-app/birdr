"""The beginners bird courses on the website: an overview and one page per lesson.

Each course is written in one language and has its own pages (Dutch: /site/vogelcursus/,
British English: /site/bird-course/). The texts around the lessons are in ``SITES``.
"""

from __future__ import annotations

import html
import json
import re

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from jizz.courses.content import LessonNotFound, course_lessons, course_payload, lesson_payload, text
from jizz.marketing.i18n import locale_from_request, localize_path
from jizz.marketing.pages import SITE_HOME, base_context, canonical_origin, dumps_json_ld

COURSE = 'nl-beginners'
LOCALE = 'nl'
UK_COURSE = 'uk-beginners'
ADVANCED_COURSE = 'nw-europe-advanced'

# What the pages say around the lesson texts, per course. "{x}" parts are filled in by the page.
SITES = {
    COURSE: {
        'locale': 'nl',
        'index_name': 'marketing-course',
        'lesson_name': 'marketing-course-lesson',
        'ui': {
            'index_title': 'Vogelcursus voor beginners: vogels van Nederland herkennen | Motmot',
            'index_description': (
                'Gratis online vogelcursus voor beginners: in twintig korte lessen leer je de vogels van '
                'Nederland herkennen, van de merel in je tuin tot de wadvogels. Met foto’s, geluiden en een quiz.'
            ),
            'crumb_course': 'Vogelcursus',
            'crumb_lesson': 'Les {week}',
            'syllabus_name': 'Les {week}: {title}',
            'lesson_title': 'Les {week}: {title} | Vogelcursus | Motmot',
            'lesson_description': '{subtitle}. Les {week} van de gratis vogelcursus voor beginners van Motmot, met foto’s, geluiden en een quiz.',
            'h1': 'Vogels van Nederland: een vogelcursus voor beginners',
            'lead': (
                'Leer in twintig korte lessen de vogels van Nederland herkennen. Je begint met de merel en de koolmees in je '
                "tuin en eindigt met de wadvogels aan de kust. Elke les duurt een minuut of tien, met foto's, geluiden en een quiz. "
                'Gratis, en zonder account.'
            ),
            'start': 'Begin met les 1',
            'how_title': 'Zo werkt een les',
            'steps': [
                ('Introductie', 'Waar we zijn en wat je gaat leren: de achtertuin, de vijver, het weiland.'),
                ('Vogel voor vogel', 'Per vogel drie dingen om op te letten, een foto en het geluid.'),
                ('Quiz', 'Pas aan het eind: herken je de vogels, ook tussen de vogels die erop lijken?'),
                ('Naar buiten', 'Een kleine opdracht voor de komende week.'),
            ],
            'all_title': 'Alle lessen',
            'all_lead': 'Doe elke week één les, in je eigen tempo. Je voortgang wordt in deze browser bewaard.',
            'parts': [(1, 'Deel 1: de basis'), (11, 'Deel 2: leefgebieden')],
            'birds_count': '{n} vogels',
            'minutes_short': '{n} min',
            'kicker': 'Vogelcursus · Les {week} · {minutes} minuten',
            'today': 'Vandaag: {n} vogels',
            'anchor': 'vogel',
            'to_quiz': 'Naar de quiz',
            'photo_by': 'Foto:',
            'unknown': 'onbekend',
            'bird_word': 'Vogel',
            'of_word': 'van',
            'look_for': 'Zo herken je hem',
            'where_when': 'Waar en wanneer',
            'recording': 'Opname:',
            'dont_confuse': 'Niet verwarren met:',
            'quiz': 'Quiz',
            'quiz_questions': '{n} vragen',
            'quiz_sound_only': ', alleen geluid',
            'quiz_with_review': ', met een paar vogels uit eerdere lessen ertussen',
            'quiz_tail': '. Je antwoorden blijven in deze browser.',
            'quiz_start': 'Start de quiz',
            'outside': 'Deze week buiten',
            'lessons_nav': 'Lessen',
            'prev': '← Les {week}',
            'all_lessons': 'Alle lessen',
            'next': 'Les {week} →',
            'sound_label': {'song': 'Zang', 'call': 'Roep', 'other': 'Geluid'},
        },
        'js': {
            'done_line': 'Klaar · {score} van {total} goed',
            'continue': 'Verder met les {week}',
            'progress': '{done} van {total} lessen klaar',
            'question_n_of': 'Vraag {n} van {total}',
            'review': ' · herhaling',
            'which_see': 'Welke vogel is dit?',
            'which_hear': 'Welke vogel hoor je?',
            'right': 'Ja, {name}.',
            'wrong': 'Dat was een {name}.',
            'next_question': 'Volgende vraag',
            'see_score': 'Bekijk je score',
            'good': 'Goed gedaan! Les {week} is klaar.',
            'try_again': 'Les {week} is klaar. Kijk de vogels die je fout had nog eens na, en probeer het opnieuw.',
            'again': 'Quiz nog een keer',
            'next_lesson': 'Naar de volgende les',
            'no_questions': 'Voor deze les zijn nog geen quizvragen.',
        },
    },
    UK_COURSE: {
        'locale': 'en',
        'index_name': 'marketing-course-uk',
        'lesson_name': 'marketing-course-uk-lesson',
        'ui': {
            'index_title': 'Bird course for beginners: learn the birds of Britain | Motmot',
            'index_description': (
                'Free online bird course for beginners: learn to recognise the birds of Britain in twenty short '
                'lessons, from the Blackbird in your garden to the waders on the coast. With photos, sounds and a quiz.'
            ),
            'crumb_course': 'Bird course',
            'crumb_lesson': 'Lesson {week}',
            'syllabus_name': 'Lesson {week}: {title}',
            'lesson_title': 'Lesson {week}: {title} | Bird course | Motmot',
            'lesson_description': '{subtitle}. Lesson {week} of Motmot’s free bird course for beginners, with photos, sounds and a quiz.',
            'h1': 'Birds of Britain: a bird course for beginners',
            'lead': (
                'Learn to recognise the birds of Britain in twenty short lessons. You start with the Blackbird and the '
                'Great Tit in your garden and finish with the waders on the coast. Each lesson takes about ten minutes, '
                'with photos, sounds and a quiz. Free, and no account needed.'
            ),
            'start': 'Start lesson 1',
            'how_title': 'How a lesson works',
            'steps': [
                ('Introduction', 'Where we are and what you will learn: the garden, the park lake, the meadow.'),
                ('Bird by bird', 'Three things to look for with each bird, a photo and its sound.'),
                ('Quiz', 'Only at the end: can you tell the birds apart, even the ones that look alike?'),
                ('Out and about', 'A small task for the week ahead.'),
            ],
            'all_title': 'All lessons',
            'all_lead': 'Do one lesson a week, at your own pace. Your progress is saved in this browser.',
            'parts': [(1, 'Part 1: the basics'), (11, 'Part 2: habitats')],
            'birds_count': '{n} birds',
            'minutes_short': '{n} min',
            'kicker': 'Bird course · Lesson {week} · {minutes} minutes',
            'today': 'Today: {n} birds',
            'anchor': 'bird',
            'to_quiz': 'Go to the quiz',
            'photo_by': 'Photo:',
            'unknown': 'unknown',
            'bird_word': 'Bird',
            'of_word': 'of',
            'look_for': 'How to recognise it',
            'where_when': 'Where and when',
            'recording': 'Recording:',
            'dont_confuse': 'Don’t confuse with:',
            'quiz': 'Quiz',
            'quiz_questions': '{n} questions',
            'quiz_sound_only': ', sound only',
            'quiz_with_review': ', with a few birds from earlier lessons mixed in',
            'quiz_tail': '. Your answers stay in this browser.',
            'quiz_start': 'Start the quiz',
            'outside': 'Out and about this week',
            'lessons_nav': 'Lessons',
            'prev': '← Lesson {week}',
            'all_lessons': 'All lessons',
            'next': 'Lesson {week} →',
            'sound_label': {'song': 'Song', 'call': 'Call', 'other': 'Sound'},
        },
        'js': {
            'done_line': 'Done · {score} of {total} right',
            'continue': 'Continue with lesson {week}',
            'progress': '{done} of {total} lessons done',
            'question_n_of': 'Question {n} of {total}',
            'review': ' · review',
            'which_see': 'Which bird is this?',
            'which_hear': 'Which bird can you hear?',
            'right': 'Yes, {name}.',
            'wrong': 'That was {name}.',
            'next_question': 'Next question',
            'see_score': 'See your score',
            'good': 'Well done! Lesson {week} is done.',
            'try_again': 'Lesson {week} is done. Have another look at the birds you got wrong, and try again.',
            'again': 'Quiz again',
            'next_lesson': 'On to the next lesson',
            'no_questions': 'There are no quiz questions for this lesson yet.',
        },
    },
    ADVANCED_COURSE: {
        'locale': 'en',
        'index_name': 'marketing-course-advanced',
        'lesson_name': 'marketing-course-advanced-lesson',
        'practice_name': 'marketing-course-advanced-practice',
        'srs': True,
        'ui': {
            'level': 'Advanced',
            'index_title': 'Advanced birding course for North-West Europe: gulls, warblers, waders and strays | Motmot',
            'index_description': (
                'Free advanced bird identification course for the UK, Ireland, the Netherlands, Germany, France and Scandinavia: '
                'big gulls, leaf warblers, stints, seabirds from land, female ducks and rarities, with photos, calls and spaced repetition.'
            ),
            'crumb_course': 'Advanced birding course',
            'crumb_lesson': 'Lesson {week}',
            'syllabus_name': 'Lesson {week}: {title}',
            'lesson_title': 'Lesson {week}: {title} | Advanced birding course | Motmot',
            'lesson_description': '{subtitle}. Lesson {week} of Motmot’s advanced birding course for North-West Europe, with photos, calls and spaced repetition.',
            'h1': 'Advanced birding: North-West Europe',
            'lead': (
                'You know a Chiffchaff from a Willow Warbler and a Dunlin from a Little Stint. Now go group by group: '
                'big gulls, Siberian leaf warblers, stints and sandpipers, seabirds from the shore in an autumn gale, '
                'female ducks, and the strays that turn up when the wind is right. Forty lessons, with photos, calls and '
                'a lot of repetition, so that the birds you have seen come back just before you forget them. Free, and no account needed.'
            ),
            'start': 'Start lesson 1',
            'practice': 'Practice',
            'how_title': 'How a lesson works',
            'steps': [
                ('Group by group', 'One family at a time: what separates the look-alikes, and the words to describe it.'),
                ('Seasons and migration', 'When each bird is here, and where in North-West Europe it is regular or a stray.'),
                ('Photos and calls', 'Questions with a photo, a recording, or both, including females, young birds and winter plumages.'),
                ('Repetition', 'Birds you get wrong come back soon; birds you know come back later. Practice has the ones that are due.'),
            ],
            'all_title': 'All lessons',
            'all_lead': 'Every fifth lesson is a review. Your progress and the birds you have to repeat are saved in this browser, and in your account when you are signed in.',
            'parts': [
                (1, 'Block 1: gulls'), (6, 'Block 2: warblers'), (11, 'Block 3: waders'), (16, 'Block 4: seabirds from land'),
                (21, 'Block 5: ducks and geese'), (26, 'Block 6: field birds'), (31, 'Block 7: strays'), (36, 'Block 8: pro'),
            ],
            'birds_count': '{n} birds',
            'minutes_short': '{n} min',
            'kicker': 'Advanced birding · Lesson {week} · {minutes} minutes',
            'today': 'Today: {n} birds',
            'anchor': 'bird',
            'to_quiz': 'Go to the quiz',
            'photo_by': 'Photo:',
            'unknown': 'unknown',
            'bird_word': 'Bird',
            'of_word': 'of',
            'look_for': 'How to recognise it',
            'where_when': 'Where and when',
            'recording': 'Recording:',
            'dont_confuse': 'Don’t confuse with:',
            'quiz': 'Quiz',
            'quiz_questions': '{n} questions',
            'quiz_sound_only': ', sound only',
            'quiz_with_review': ', with birds you have to repeat mixed in',
            'quiz_tail': '. Your answers decide when each bird comes back.',
            'quiz_start': 'Start the quiz',
            'outside': 'Out and about this week',
            'lessons_nav': 'Lessons',
            'prev': '← Lesson {week}',
            'all_lessons': 'All lessons',
            'next': 'Lesson {week} →',
            'sound_label': {'song': 'Song', 'call': 'Call', 'other': 'Sound'},
            'practice_title': 'Practice',
            'practice_lead': 'Ten questions with the birds that are due to come back. Right answers push a bird further away, wrong answers bring it back tomorrow.',
            'practice_start': 'Start practice',
            'practice_back': 'Back to the course',
        },
        'js': {
            'done_line': 'Done · {score} of {total} right',
            'continue': 'Continue with lesson {week}',
            'progress': '{done} of {total} lessons done',
            'question_n_of': 'Question {n} of {total}',
            'review': ' · repeat',
            'which_see': 'Which bird is this?',
            'which_hear': 'Which bird can you hear?',
            'which_both': 'Which bird is this? Look and listen.',
            'right': 'Yes, {name}.',
            'wrong': 'That was {name}.',
            'next_question': 'Next question',
            'see_score': 'See your score',
            'good': 'Well done! Lesson {week} is done.',
            'try_again': 'Lesson {week} is done. Have another look at the birds you got wrong, and try again.',
            'again': 'Quiz again',
            'next_lesson': 'On to the next lesson',
            'no_questions': 'There are no quiz questions for this lesson yet.',
            'show_plumage': True,
            'photo_shows': 'This photo shows: {label}.',
            'loading': 'Loading…',
            'due_count': '{n} birds to repeat',
            'none_due': 'Nothing is due right now. Come back later, or revisit a lesson.',
        },
        'practice_js': {
            'good': 'Well done! Practice is done.',
            'try_again': 'Practice is done. The birds you got wrong will be back soon.',
            'again': 'Practise again',
            'next_lesson': 'Back to the course',
        },
    },
}


def _fmt(template: str, **values) -> str:
    return template.format(**values)


def _js_ui(course: str, **overrides) -> dict:
    """The texts and keys the page scripts need; courses with spaced repetition also get their storage keys."""
    site = SITES[course]
    ui = {**site['js'], 'storage_key': f'course:{course}:progress', **overrides}
    if site.get('srs'):
        ui['srs_key'] = f'course:{course}:srs'
        ui['api_base'] = f'/api/courses/{course}'
    return ui


def lesson_slug(lesson: dict, course: str = COURSE) -> str:
    return slugify(text(lesson['title'], SITES[course]['locale']))


def lesson_path(week: int, course: str = COURSE) -> str:
    lesson = next(l for l in course_lessons(course) if l['week'] == week)
    return reverse(SITES[course]['lesson_name'], kwargs={'week': week, 'slug': lesson_slug(lesson, course)})


def course_paths(course: str = COURSE) -> list[str]:
    """Logical paths of a course's pages, for the sitemap (each served in its own language only)."""
    return [reverse(SITES[course]['index_name'])] + [lesson_path(l['week'], course) for l in course_lessons(course)]


def all_course_paths() -> list[str]:
    return [path for course in SITES for path in course_paths(course)]


def course_path_locales() -> dict[str, tuple[str, ...]]:
    """The one language each course page exists in."""
    return {path: (SITES[course]['locale'],) for course in SITES for path in course_paths(course)}


def _bold(value: str) -> str:
    """Escape, then turn "**word**" into <strong>word</strong>."""
    return mark_safe(re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(value or '')))


def _paragraphs(value: str) -> list[str]:
    return [_bold(p) for p in re.split(r'\n\s*\n', value or '') if p.strip()]


def _own_language_only(request, path: str, locale: str):
    """A course is written in one language: other languages go to that course page."""
    if locale_from_request(request) != locale:
        query = request.META.get('QUERY_STRING')
        return redirect(localize_path(path, locale) + (f'?{query}' if query else ''))
    return None


def _context(request, *, title, description, path, breadcrumbs, extra_json_ld=None, **extra):
    context = base_context(
        request, title=title, description=description, path=path, breadcrumbs=breadcrumbs,
        extra_json_ld=extra_json_ld, **extra,
    )
    # One language only: no hreflang alternates, and x-default is the course page itself.
    context['locale_alternates'] = []
    context['hreflang_alternates'] = []
    context['locale_default_url'] = context['canonical_url']
    context['nav_section'] = 'course'
    return context


def _course_index(request, course: str):
    site = SITES[course]
    locale, ui = site['locale'], site['ui']
    path = reverse(site['index_name'])
    if response := _own_language_only(request, path, locale):
        return response
    payload = course_payload(course, locale)
    parts = dict(ui['parts'])
    part_starts = sorted(parts)
    lessons = []
    for row in payload['lessons']:
        week = row['week']
        is_start = week in parts
        is_end = week + 1 in parts or week == payload['lessons'][-1]['week']
        meta = row['subtitle']
        if row['bird_count']:
            meta += ' · ' + _fmt(ui['birds_count'], n=row['bird_count'])
        meta += ' · ' + _fmt(ui['minutes_short'], n=row['minutes'])
        lessons.append({
            **row,
            'href': localize_path(lesson_path(week, course), locale),
            'meta': meta,
            'part_heading': parts.get(week, ''),
            'opens_list': is_start,
            'closes_list': is_end,
        })
    origin = canonical_origin(request)
    course_ld = {
        '@context': 'https://schema.org',
        '@type': 'Course',
        'name': payload['title'],
        'description': payload['subtitle'],
        'inLanguage': locale,
        'educationalLevel': ui.get('level', 'Beginner'),
        'isAccessibleForFree': True,
        'url': origin + localize_path(path, locale),
        'provider': {'@type': 'Organization', 'name': 'Motmot', 'url': origin + SITE_HOME},
        'hasCourseInstance': {'@type': 'CourseInstance', 'courseMode': 'online', 'courseWorkload': 'PT10M'},
        'syllabusSections': [
            {
                '@type': 'Syllabus',
                'name': _fmt(ui['syllabus_name'], week=row['week'], title=row['title']),
                'description': row['subtitle'],
            }
            for row in payload['lessons']
        ],
    }
    context = _context(
        request,
        title=ui['index_title'],
        description=ui['index_description'],
        path=path,
        breadcrumbs=[('Home', SITE_HOME), (ui['crumb_course'], path)],
        extra_json_ld=[course_ld],
        course=payload,
        lessons=lessons,
        ui=ui,
        js_ui=_js_ui(course),
        practice_href=localize_path(reverse(site['practice_name']), locale) if site.get('srs') else '',
    )
    return render(request, 'marketing/course_index.html', context)


def _course_lesson(request, course: str, week: int, slug: str):
    site = SITES[course]
    locale, ui = site['locale'], site['ui']
    try:
        payload = lesson_payload(course, week, locale)
    except LessonNotFound:
        raise Http404
    path = lesson_path(week, course)
    if slug != lesson_slug(next(l for l in course_lessons(course) if l['week'] == week), course):
        return redirect(localize_path(path, locale), permanent=True)
    if response := _own_language_only(request, path, locale):
        return response

    birds = []
    for bird in payload['birds']:
        compare = payload['compare'] if payload['compare'] and payload['compare']['after_species_id'] == bird['species_id'] else None
        pair = []
        if compare:
            by_id = {b['species_id']: b for b in payload['birds']}
            pair = [by_id[i] for i in compare['species_ids'] if i in by_id]
        bold = {m.lower() for line in bird['look_for'] for m in re.findall(r'\*\*(.+?)\*\*', line)}
        words = [
            w for w in payload['words']
            if any(b.startswith(w['term'].lower()[:max(4, len(w['term']) - 2)]) for b in bold)
        ]
        labels = ui['sound_label']
        birds.append({
            **bird,
            'look_for_html': [_bold(line) for line in bird['look_for']],
            'words': words,
            'compare': compare,
            'pair': pair,
            'photo': bird['images'][0] if bird['images'] else None,
            'sound_label': labels.get(bird['sound']['type'], labels['other']),
        })

    weeks = [l['week'] for l in course_lessons(course)]
    prev_week = week - 1 if week - 1 in weeks else None
    next_week = week + 1 if week + 1 in weeks else None
    quiz_data = {
        key: payload[key]
        for key in ('week', 'kind', 'birds', 'quiz', 'review_birds', 'known_species', 'lookalikes')
    }
    quiz = payload['quiz']
    quiz_intro = _fmt(ui['quiz_questions'], n=quiz['questions'])
    if quiz['kind'] == 'sound':
        quiz_intro += ui['quiz_sound_only']
    if quiz['review_questions'] and payload['kind'] != 'review':
        quiz_intro += ui['quiz_with_review']
    quiz_intro += ui['quiz_tail']
    course_path = reverse(site['index_name'])
    context = _context(
        request,
        title=_fmt(ui['lesson_title'], week=week, title=payload['title']),
        description=_fmt(ui['lesson_description'], subtitle=payload['subtitle'], week=week),
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            (ui['crumb_course'], course_path),
            (_fmt(ui['crumb_lesson'], week=week), path),
        ],
        lesson=payload,
        intro_html=_paragraphs(payload['intro']),
        birds=birds,
        course_href=localize_path(course_path, locale),
        prev_href=localize_path(lesson_path(prev_week, course), locale) if prev_week else '',
        next_href=localize_path(lesson_path(next_week, course), locale) if next_week else '',
        next_week=next_week,
        quiz_json=mark_safe(json.dumps(quiz_data, ensure_ascii=False).replace('</', '<\\/')),
        ui=ui,
        js_ui=_js_ui(course),
        kicker=_fmt(ui['kicker'], week=week, minutes=payload['minutes']),
        today=_fmt(ui['today'], n=len(birds)),
        quiz_intro=quiz_intro,
        prev_label=_fmt(ui['prev'], week=week - 1),
        next_label=_fmt(ui['next'], week=next_week) if next_week else '',
    )
    return render(request, 'marketing/course_lesson.html', context)


def _course_practice(request, course: str):
    """Ten questions with the birds that are due, from the spaced repetition in this browser."""
    site = SITES[course]
    locale, ui = site['locale'], site['ui']
    path = reverse(site['practice_name'])
    if response := _own_language_only(request, path, locale):
        return response
    course_path = reverse(site['index_name'])
    context = _context(
        request,
        title=f"{ui['practice_title']} | {ui['crumb_course']} | Motmot",
        description=ui['practice_lead'],
        path=path,
        breadcrumbs=[('Home', SITE_HOME), (ui['crumb_course'], course_path), (ui['practice_title'], path)],
        ui=ui,
        js_ui=_js_ui(course, **site.get('practice_js', {})),
        course_href=localize_path(course_path, locale),
    )
    context['noindex'] = True
    return render(request, 'marketing/course_practice.html', context)


@require_GET
def course_index(request):
    return _course_index(request, COURSE)


@require_GET
def course_lesson(request, week: int, slug: str):
    return _course_lesson(request, COURSE, week, slug)


@require_GET
def course_index_uk(request):
    return _course_index(request, UK_COURSE)


@require_GET
def course_lesson_uk(request, week: int, slug: str):
    return _course_lesson(request, UK_COURSE, week, slug)


@require_GET
def course_index_advanced(request):
    return _course_index(request, ADVANCED_COURSE)


@require_GET
def course_lesson_advanced(request, week: int, slug: str):
    return _course_lesson(request, ADVANCED_COURSE, week, slug)


@require_GET
def course_practice_advanced(request):
    return _course_practice(request, ADVANCED_COURSE)
