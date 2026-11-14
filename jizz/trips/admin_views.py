"""Admin API for choosing the photos of a trip prep pack: candidates per species and saving picks."""

from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.courses.admin_views import MAX_CARD, _candidate
from jizz.courses.content import text
from jizz.models import Species, TripPhotoPick
from jizz.trips.api import _static_files, clear_cache, photo_picks
from jizz.trips.content import TRIPS, country_dir, resolve_trip
from media.models import Media


def _trip(code):
    code = resolve_trip(code)
    if code not in TRIPS:
        raise Http404
    return code


class TripPhotosView(APIView):
    """Every bird of the pack by unit, with the photos in media.json and the admin picks."""

    permission_classes = [IsAdminUser]

    def get(self, request, country):
        trip = _trip(country)
        files = _static_files(trip)
        picks = photo_picks(trip)
        media = files['media']
        ids = {e['species_id'] for e in media.values() if e.get('species_id')}
        species = {s.id: s for s in Species.objects.filter(id__in=ids)}
        names = {}
        for unit in files['units']['units']:
            names[unit['slug']] = text(files['texts'].get('units', {}).get(unit['slug'], {}).get('title'), 'en') or unit['slug']

        def bird(code):
            entry = media.get(code, {})
            sp = species.get(entry.get('species_id'))
            if sp is None:
                return None
            return {
                'species_id': sp.id,
                'code': code,
                'name': sp.name,
                'name_nl': sp.name_nl or '',
                'latin': sp.name_latin or '',
                'file': {'card': entry.get('card', []), 'quiz': entry.get('quiz', [])},
                'pick': picks.get(sp.id),
            }

        seen = set()
        sections = []
        for unit in files['units']['units']:
            birds = []
            for code in unit['species']:
                b = bird(code)
                if b and code not in seen:
                    seen.add(code)
                    birds.append(b)
            sections.append({'slug': unit['slug'], 'title': names[unit['slug']], 'birds': birds})
        # Birds in no unit (e.g. a lookalike home bird) still need photos.
        rest = [b for b in (bird(c) for c in media if c not in seen) if b]
        if rest:
            sections.append({'slug': 'other', 'title': 'Other birds', 'birds': rest})
        return Response({
            'trip': trip,
            'name': text(TRIPS[trip]['name'], 'en'),
            'trips': [
                {'code': c, 'name': text(m['name'], 'en'), 'parent': m.get('parent')}
                for c, m in TRIPS.items()
                if (country_dir(c) / 'media.json').exists()
            ],
            'sections': sections,
        })


class TripSpeciesMediaView(APIView):
    """Visible photos of one species, best reviewed first (same list as the course page)."""

    permission_classes = [IsAdminUser]

    def get(self, request, country, species_id):
        _trip(country)
        from django.db.models import Count, Q

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


class TripCommonsPhotoView(APIView):
    """Add a photo from Wikimedia Commons to a species, so it can be picked."""

    permission_classes = [IsAdminUser]

    def post(self, request, country, species_id):
        from media.commons_import import CommonsImportError, add_commons_photo

        _trip(country)
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


class TripPhotoPickView(APIView):
    """Save the photos chosen for one bird of one pack."""

    permission_classes = [IsAdminUser]

    def put(self, request, country, species_id):
        trip = _trip(country)
        files = _static_files(trip)
        if not any(e.get('species_id') == species_id for e in files['media'].values()):
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
        pick, _ = TripPhotoPick.objects.update_or_create(
            trip=trip,
            species_id=species_id,
            defaults={**lists, 'done': bool(data.get('done', False)), 'updated_by': request.user},
        )
        clear_cache(trip)
        return Response({'card': pick.card, 'quiz': pick.quiz, 'reject': pick.reject, 'done': pick.done})
