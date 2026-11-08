"""Admin API for choosing the photos of a course: candidates per species and saving picks."""

import re

from django.db.models import Count, Q
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.courses.content import COURSES, clear_cache, course_lessons, photo_picks, text
from jizz.models import CoursePhotoPick, Species
from media.display_urls import media_object_display_url
from media.models import Media

MAX_CARD = 3


def _course(slug):
    if slug not in COURSES:
        raise Http404
    return slug


def _thumb(url: str | None) -> str | None:
    """A small version for the grid: iNaturalist 'small', Flickr 320px; others as they are."""
    if not url:
        return url
    url = re.sub(r'/(original|large|medium)\.(jpe?g|png)$', r'/small.\2', url)
    return re.sub(r'(staticflickr\.com/.+)_[a-z]\.jpg$', r'\1_n.jpg', url)


class CoursePhotosView(APIView):
    """Every bird of every lesson, with the photos the lesson file has and the admin picks."""

    permission_classes = [IsAdminUser]

    def get(self, request, slug):
        _course(slug)
        picks = photo_picks(slug)
        lessons = []
        for lesson in course_lessons(slug):
            birds = []
            for bird in lesson.get('birds', []):
                media = bird.get('media', {})
                pick = picks.get((lesson['week'], bird['species_id']))
                birds.append({
                    'species_id': bird['species_id'],
                    'name': text(bird['name'], 'nl'),
                    'latin': bird.get('latin', ''),
                    'plumage': text(bird.get('plumage'), 'nl'),
                    'file': {'card': media.get('card', []), 'quiz': media.get('quiz', [])},
                    'pick': pick,
                })
            lessons.append({'week': lesson['week'], 'title': text(lesson['title'], 'nl'), 'birds': birds})
        return Response({'course': slug, 'lessons': lessons})


class CourseSpeciesMediaView(APIView):
    """Visible photos of one species, best reviewed first."""

    permission_classes = [IsAdminUser]

    def get(self, request, slug, species_id):
        _course(slug)
        rows = (
            Media.objects.filter(species_id=species_id, type='image', hide=False)
            .annotate(
                approved=Count('reviews', filter=Q(reviews__review_type='approved')),
                rejected=Count('reviews', filter=Q(reviews__review_type='rejected')),
            )
            .order_by('-created')
        )
        media = [_candidate(m, m.approved, m.rejected) for m in rows]
        media.sort(key=lambda m: -(m['approved'] - 2 * m['rejected']))
        return Response({'species_id': species_id, 'media': media})


def _candidate(m, approved=0, rejected=0):
    url = media_object_display_url(m)
    return {
        'id': m.id,
        'url': url,
        'thumb': _thumb(url),
        'link': m.link,
        'contributor': re.sub(r'<[^>]+>', '', m.contributor or '').strip(),
        'license': m.copyright_standardized,
        'source': m.source,
        'approved': approved,
        'rejected': rejected,
    }


class CourseCommonsPhotoView(APIView):
    """Add a photo from Wikimedia Commons to a species, so it can be picked for the course."""

    permission_classes = [IsAdminUser]

    def post(self, request, slug, species_id):
        from media.commons_import import CommonsImportError, add_commons_photo

        _course(slug)
        species = Species.objects.filter(id=species_id).first()
        if species is None:
            raise Http404
        try:
            media, created = add_commons_photo(species, str(request.data.get('link', '')))
        except CommonsImportError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'photo': _candidate(media), 'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CoursePhotoPickView(APIView):
    """Save the photos chosen for one bird of one lesson."""

    permission_classes = [IsAdminUser]

    def put(self, request, slug, week, species_id):
        _course(slug)
        lesson = next((l for l in course_lessons(slug) if l['week'] == week), None)
        if not lesson or not any(b['species_id'] == species_id for b in lesson.get('birds', [])):
            raise Http404
        data = request.data
        lists = {}
        for key in ('card', 'quiz', 'reject'):
            value = data.get(key, [])
            if not isinstance(value, list) or not all(isinstance(i, int) for i in value):
                return Response({'error': f'{key} must be a list of media ids.'}, status=status.HTTP_400_BAD_REQUEST)
            lists[key] = list(dict.fromkeys(value))
        if len(lists['card']) > MAX_CARD:
            return Response({'error': f'At most {MAX_CARD} card photos.'}, status=status.HTTP_400_BAD_REQUEST)
        used = set(lists['card']) | set(lists['quiz']) | set(lists['reject'])
        if len(used) != sum(len(v) for v in lists.values()):
            return Response({'error': 'A photo can have only one role.'}, status=status.HTTP_400_BAD_REQUEST)
        known = set(Media.objects.filter(id__in=used, species_id=species_id, type='image').values_list('id', flat=True))
        if used - known:
            return Response(
                {'error': 'These photos are not images of this species.', 'ids': sorted(used - known)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not Species.objects.filter(id=species_id).exists():
            raise Http404
        pick, _ = CoursePhotoPick.objects.update_or_create(
            course=slug,
            week=week,
            species_id=species_id,
            defaults={**lists, 'done': bool(data.get('done', False)), 'updated_by': request.user},
        )
        clear_cache(slug)
        return Response({'card': pick.card, 'quiz': pick.quiz, 'reject': pick.reject, 'done': pick.done})
