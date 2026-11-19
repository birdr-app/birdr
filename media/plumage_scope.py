"""Which photos a plumage command works on: media ids, species, or a whole course.

`--approved` narrows any scope to photos whose latest review is an approval.
`--course` means every photo id the course's lesson files reference (the lesson files and the
admin picks of `effective_lessons`), plus all visible photos of the course's species.
"""
from __future__ import annotations

from typing import Iterable, Optional, Set, Tuple

from django.core.management.base import CommandError
from django.db.models import OuterRef, Q, QuerySet, Subquery

from media.models import Media, MediaReview


def add_scope_arguments(parser) -> None:
    parser.add_argument('--course', help='Course slug: its referenced photos and all visible photos of its species.')
    parser.add_argument('--species', action='append', default=[],
                        help='Species id, code or latin name (repeatable, or comma separated).')
    parser.add_argument('--approved', action='store_true',
                        help='Only photos whose latest review is "approved" (alone: all approved photos; '
                             'with another scope: that scope narrowed to approved photos).')
    parser.add_argument('--media-ids', action='append', default=[], help='Media ids, comma separated (repeatable).')


def course_scope(slug: str) -> Tuple[Set[int], Set[int]]:
    """(photo ids referenced by the course, species ids of the course)."""
    from jizz.courses.content import COURSES, course_lessons, effective_lessons

    if slug not in COURSES:
        raise CommandError(f'Unknown course {slug!r}. Known: {", ".join(sorted(COURSES))}')
    media_ids: Set[int] = set()
    species_ids: Set[int] = set()
    for lessons in (course_lessons(slug), effective_lessons(slug)):
        for lesson in lessons:
            for bird in lesson.get('birds', []):
                species_ids.add(bird['species_id'])
                media = bird.get('media') or {}
                media_ids.update(media.get('card', []))
                media_ids.update(media.get('quiz', []))
    return media_ids, species_ids


def resolve_species(values: Iterable[str]) -> Set[int]:
    from jizz.models import Species

    ids: Set[int] = set()
    for chunk in values:
        for raw in str(chunk).split(','):
            raw = raw.strip()
            if not raw:
                continue
            if raw.isdigit():
                species = Species.objects.filter(id=int(raw)).first()
            else:
                species = (Species.objects.filter(code__iexact=raw).first()
                           or Species.objects.filter(name_latin__iexact=raw).first())
            if species is None:
                raise CommandError(f'Unknown species {raw!r}')
            ids.add(species.id)
    return ids


def parse_media_ids(values: Iterable[str]) -> Set[int]:
    out: Set[int] = set()
    for chunk in values:
        for raw in str(chunk).split(','):
            if raw.strip():
                try:
                    out.add(int(raw))
                except ValueError as exc:
                    raise CommandError(f'Not a media id: {raw!r}') from exc
    return out


def is_scoped(opts) -> bool:
    return bool(opts.get('course') or opts.get('species') or opts.get('media_ids') or opts.get('approved'))


def only_approved(qs: QuerySet) -> QuerySet:
    """Photos whose latest review is an approval (the same rule as `Media.effective_review_status`)."""
    latest = MediaReview.objects.filter(media=OuterRef('pk')).order_by('-id').values('review_type')[:1]
    return qs.annotate(latest_review=Subquery(latest)).filter(latest_review=MediaReview.APPROVED)


def scoped_media(opts) -> Optional[QuerySet]:
    """Image media of the requested scope, or None when no scope was given."""
    if not is_scoped(opts):
        return None
    explicit = bool(opts.get('course') or opts.get('species') or opts.get('media_ids'))
    media_ids = parse_media_ids(opts.get('media_ids') or [])
    species_ids = resolve_species(opts.get('species') or [])
    if opts.get('course'):
        course_media, course_species = course_scope(opts['course'])
        media_ids |= course_media
        species_ids |= course_species
    qs = Media.objects.filter(type='image')
    if explicit:
        qs = qs.filter(Q(id__in=media_ids) | Q(species_id__in=species_ids, hide=False))
    else:
        qs = qs.filter(hide=False)
    return only_approved(qs) if opts.get('approved') else qs
