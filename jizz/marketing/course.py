"""The beginners bird course on the website: an overview and one page per lesson (Dutch only)."""

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


def lesson_slug(lesson: dict) -> str:
    return slugify(text(lesson['title'], LOCALE))


def lesson_path(week: int) -> str:
    lesson = next(l for l in course_lessons(COURSE) if l['week'] == week)
    return reverse('marketing-course-lesson', kwargs={'week': week, 'slug': lesson_slug(lesson)})


def course_paths() -> list[str]:
    """Logical paths of the course pages, for the sitemap (served in Dutch only)."""
    return [reverse('marketing-course')] + [lesson_path(l['week']) for l in course_lessons(COURSE)]


def _bold(value: str) -> str:
    """Escape, then turn "**word**" into <strong>word</strong>."""
    return mark_safe(re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(value or '')))


def _paragraphs(value: str) -> list[str]:
    return [_bold(p) for p in re.split(r'\n\s*\n', value or '') if p.strip()]


def _dutch_only(request, path: str):
    """The course is written in Dutch: other languages go to the Dutch page."""
    if locale_from_request(request) != LOCALE:
        query = request.META.get('QUERY_STRING')
        return redirect(localize_path(path, LOCALE) + (f'?{query}' if query else ''))
    return None


def _context(request, *, title, description, path, breadcrumbs, extra_json_ld=None, **extra):
    context = base_context(
        request, title=title, description=description, path=path, breadcrumbs=breadcrumbs,
        extra_json_ld=extra_json_ld, **extra,
    )
    # One language only: no hreflang alternates, and x-default is the Dutch page itself.
    context['locale_alternates'] = []
    context['locale_default_url'] = context['canonical_url']
    context['nav_section'] = 'course'
    return context


@require_GET
def course_index(request):
    path = reverse('marketing-course')
    if response := _dutch_only(request, path):
        return response
    course = course_payload(COURSE, LOCALE)
    lessons = [
        {**row, 'href': localize_path(lesson_path(row['week']), LOCALE)}
        for row in course['lessons']
    ]
    origin = canonical_origin(request)
    course_ld = {
        '@context': 'https://schema.org',
        '@type': 'Course',
        'name': course['title'],
        'description': course['subtitle'],
        'inLanguage': 'nl',
        'educationalLevel': 'Beginner',
        'isAccessibleForFree': True,
        'url': origin + localize_path(path, LOCALE),
        'provider': {'@type': 'Organization', 'name': 'Motmot', 'url': origin + SITE_HOME},
        'hasCourseInstance': {'@type': 'CourseInstance', 'courseMode': 'online', 'courseWorkload': 'PT10M'},
        'syllabusSections': [
            {'@type': 'Syllabus', 'name': f"Les {row['week']}: {row['title']}", 'description': row['subtitle']}
            for row in course['lessons']
        ],
    }
    context = _context(
        request,
        title='Vogelcursus voor beginners: vogels van Nederland herkennen | Motmot',
        description=(
            'Gratis online vogelcursus voor beginners: in twintig korte lessen leer je de vogels van '
            'Nederland herkennen, van de merel in je tuin tot de wadvogels. Met foto’s, geluiden en een quiz.'
        ),
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Vogelcursus', path)],
        extra_json_ld=[course_ld],
        course=course,
        lessons=lessons,
    )
    return render(request, 'marketing/course_index.html', context)


@require_GET
def course_lesson(request, week: int, slug: str):
    try:
        payload = lesson_payload(COURSE, week, LOCALE)
    except LessonNotFound:
        raise Http404
    path = lesson_path(week)
    if slug != lesson_slug(next(l for l in course_lessons(COURSE) if l['week'] == week)):
        return redirect(localize_path(path, LOCALE), permanent=True)
    if response := _dutch_only(request, path):
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
        birds.append({
            **bird,
            'look_for_html': [_bold(line) for line in bird['look_for']],
            'words': words,
            'compare': compare,
            'pair': pair,
            'photo': bird['images'][0] if bird['images'] else None,
            'sound_label': {'song': 'Zang', 'call': 'Roep'}.get(bird['sound']['type'], 'Geluid'),
        })

    weeks = [l['week'] for l in course_lessons(COURSE)]
    prev_week = week - 1 if week - 1 in weeks else None
    next_week = week + 1 if week + 1 in weeks else None
    quiz_data = {
        key: payload[key]
        for key in ('week', 'kind', 'birds', 'quiz', 'review_birds', 'known_species', 'lookalikes')
    }
    context = _context(
        request,
        title=f"Les {week}: {payload['title']} | Vogelcursus | Motmot",
        description=f"{payload['subtitle']}. Les {week} van de gratis vogelcursus voor beginners van Motmot, met foto’s, geluiden en een quiz.",
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Vogelcursus', reverse('marketing-course')), (f'Les {week}', path)],
        lesson=payload,
        intro_html=_paragraphs(payload['intro']),
        birds=birds,
        course_href=localize_path(reverse('marketing-course'), LOCALE),
        prev_href=localize_path(lesson_path(prev_week), LOCALE) if prev_week else '',
        next_href=localize_path(lesson_path(next_week), LOCALE) if next_week else '',
        next_week=next_week,
        quiz_json=mark_safe(json.dumps(quiz_data, ensure_ascii=False).replace('</', '<\\/')),
    )
    return render(request, 'marketing/course_lesson.html', context)

