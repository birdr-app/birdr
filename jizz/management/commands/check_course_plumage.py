"""Check that the photos of a course show the plumage the lesson files ask for.

A lesson file can say, per bird, `"plumage_filter": {"sex": "female"}` (also `stage`, `season`; a
list of values is allowed). Every photo in that bird's effective card and quiz lists
(`effective_lessons`, so the admin picks count) must then have a plumage label that matches the
filter and can be trusted: a human label, or a confidence of at least --min-confidence (a label
from an image source counts as `SOURCE_CONFIDENCE`, 0.9).

A lesson with `"plumage_required": true` is a lesson that depends on plumage: its birds without a
plumage_filter are listed as warnings (they cannot be asked for "only females"), they do not fail.

Offenders are printed per week and species; the exit status is 1 when there are any.
"""
from django.core.management.base import BaseCommand, CommandError

from jizz.courses.content import COURSES, effective_lessons
from media.models import Media, MediaPlumage
from media.plumage import FIELD_VALUES, FIELDS, effective_confidence


def _wanted(plumage_filter: dict) -> dict:
    """{field: set of accepted values}; raises ValueError for an unknown field or value."""
    wanted = {}
    for field, value in plumage_filter.items():
        if field not in FIELDS:
            raise ValueError(f'unknown filter field "{field}"')
        values = {value} if isinstance(value, str) else set(value)
        if not values or values - set(FIELD_VALUES[field]):
            raise ValueError(f'invalid {field} filter {value!r}')
        wanted[field] = values
    return wanted


def problem_with(media, plumage, wanted: dict, min_confidence: float):
    """Why a photo does not satisfy a filter, or None when it does."""
    if media is None:
        return 'photo does not exist'
    if media.hide:
        return 'photo is hidden'
    if plumage is None:
        return 'no plumage label'
    for field, values in wanted.items():
        have = getattr(plumage, field)
        if have not in values:
            return f'{field} is {have or "empty"}, wanted {"/".join(sorted(values))} ({plumage.source})'
    confidence = effective_confidence(plumage)
    if plumage.source != 'human' and confidence < min_confidence:
        return f'{plumage.source} label has confidence {confidence:.2f} < {min_confidence:g}; confirm it by hand'
    return None


class Command(BaseCommand):
    help = 'Check the photos of birds with a plumage_filter against their plumage labels.'

    def add_arguments(self, parser):
        parser.add_argument('course')
        parser.add_argument('--min-confidence', type=float, default=0.8)

    def handle(self, *args, **opts):
        slug, threshold = opts['course'], opts['min_confidence']
        if slug not in COURSES:
            raise CommandError(f'Unknown course {slug!r}. Known: {", ".join(sorted(COURSES))}')
        lessons = effective_lessons(slug)

        checks = []  # (lesson, bird, wanted | error string)
        warnings = []
        for lesson in lessons:
            for bird in lesson.get('birds', []):
                if 'plumage_filter' in bird:
                    try:
                        checks.append((lesson, bird, _wanted(bird['plumage_filter'])))
                    except (ValueError, TypeError, AttributeError) as exc:
                        checks.append((lesson, bird, str(exc)))
                elif lesson.get('plumage_required'):
                    warnings.append((lesson, bird))

        ids = {i for _, bird, _ in checks for i in self._photo_ids(bird)}
        media = {m.id: m for m in Media.objects.filter(id__in=ids)}
        plumage = {p.media_id: p for p in MediaPlumage.objects.filter(media_id__in=ids)}

        offenders = 0
        checked = 0
        for lesson, bird, wanted in checks:
            name = self._name(bird)
            if isinstance(wanted, str):
                offenders += 1
                self.stdout.write(f'week {lesson["week"]} {name}: invalid plumage_filter ({wanted})')
                continue
            for role in ('card', 'quiz'):
                for media_id in (bird.get('media') or {}).get(role, []):
                    checked += 1
                    why = problem_with(media.get(media_id), plumage.get(media_id), wanted, threshold)
                    if why:
                        offenders += 1
                        self.stdout.write(f'week {lesson["week"]} {name}: {role} photo {media_id}: {why}')
        for lesson, bird in warnings:
            self.stdout.write(f'warning: week {lesson["week"]} {self._name(bird)}: lesson is plumage_required '
                              f'but the bird has no plumage_filter')

        self.stdout.write(f'{len(checks)} birds with a plumage filter, {checked} photos checked, '
                          f'{offenders} offending')
        if offenders:
            raise CommandError(f'{offenders} photos do not match their plumage filter')
        self.stdout.write(self.style.SUCCESS('All photos match their plumage filter.'))

    @staticmethod
    def _photo_ids(bird):
        media = bird.get('media') or {}
        return list(media.get('card', [])) + list(media.get('quiz', []))

    @staticmethod
    def _name(bird):
        name = bird.get('name')
        if isinstance(name, dict):
            name = name.get('en') or name.get('nl') or next(iter(name.values()), '')
        return name or f'species {bird.get("species_id")}'
