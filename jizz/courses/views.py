"""Course API: public content, plus per-user progress that syncs across devices."""

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.courses.content import COURSES, LessonNotFound, course_payload, lesson_payload, srs_pool

CACHE_SECONDS = 10 * 60


def _lang(request, slug: str) -> str:
    wanted = (request.query_params.get('lang') or '').lower()
    languages = COURSES[slug]['languages']
    return wanted if wanted in languages else languages[0]


class CourseDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        if slug not in COURSES:
            raise Http404
        lang = _lang(request, slug)
        key = f'course:{slug}:{lang}'
        payload = cache.get(key)
        if payload is None:
            payload = course_payload(slug, lang)
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


class CourseLessonView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug, week):
        if slug not in COURSES:
            raise Http404
        lang = _lang(request, slug)
        key = f'course:{slug}:{week}:{lang}'
        payload = cache.get(key)
        if payload is None:
            try:
                payload = lesson_payload(slug, week, lang)
            except LessonNotFound:
                raise Http404
            cache.set(key, payload, CACHE_SECONDS)
        return Response(payload)


def _progress_payload(user, slug: str) -> dict:
    from jizz.models import CourseLessonResult

    rows = CourseLessonResult.objects.filter(user=user, course=slug)
    return {
        'completed': {
            str(r.week): {'score': r.score, 'total': r.total, 'completedAt': r.completed_at.isoformat()}
            for r in rows
        }
    }


class CourseProgressView(APIView):
    """GET the signed-in user's lesson results; POST results to merge in (best score per lesson wins)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        if slug not in COURSES:
            raise Http404
        return Response(_progress_payload(request.user, slug))

    def post(self, request, slug):
        from jizz.models import CourseLessonResult

        if slug not in COURSES:
            raise Http404
        results = request.data.get('results')
        if not isinstance(results, list) or len(results) > 100:
            return Response({'detail': 'Send results as a list of up to 100.'}, status=400)
        for row in results:
            try:
                week, score, total = int(row['week']), int(row['score']), int(row['total'])
            except (KeyError, TypeError, ValueError):
                return Response({'detail': 'Each result needs week, score and total.'}, status=400)
            if not (1 <= week <= 200 and 0 <= score <= total <= 1000):
                return Response({'detail': 'Result out of range.'}, status=400)
            completed_at = parse_datetime(str(row.get('completedAt') or '')) or timezone.now()
            if timezone.is_naive(completed_at):
                completed_at = timezone.make_aware(completed_at)
            existing = CourseLessonResult.objects.filter(user=request.user, course=slug, week=week).first()
            if existing is None:
                CourseLessonResult.objects.create(
                    user=request.user, course=slug, week=week, score=score, total=total, completed_at=completed_at,
                )
            elif score >= existing.score:
                existing.score, existing.total, existing.completed_at = score, total, completed_at
                existing.save()
        return Response(_progress_payload(request.user, slug))


MAX_PRACTICE_KEYS = 40
MAX_SRS_ITEMS = 1000
SRS_BOXES = 6  # box 0 is "just got it wrong"; box 6 is the longest interval


class CoursePracticeBirdsView(APIView):
    """Quiz material for the birds a learner has to repeat: GET ?key=8861|adult female&key=..."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        if slug not in COURSES:
            raise Http404
        keys = request.query_params.getlist('key')[:MAX_PRACTICE_KEYS]
        return Response(srs_pool(slug, keys, _lang(request, slug)))


def _srs_payload(user, slug: str) -> dict:
    from jizz.models import CourseBirdResult

    rows = CourseBirdResult.objects.filter(user=user, course=slug)
    return {
        'birds': {
            f'{r.species_id}|{r.plumage}': {
                'box': r.box, 'due': r.due_at.isoformat(), 'seen': r.last_seen.isoformat(),
                'right': r.right, 'wrong': r.wrong,
            }
            for r in rows
        }
    }


def _parse_srs_time(value):
    parsed = parse_datetime(str(value or ''))
    if parsed is None:
        raise ValueError(value)
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


class CourseSrsView(APIView):
    """GET the signed-in user's spaced repetition state; POST state to merge in (latest seen wins per bird)."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        if slug not in COURSES:
            raise Http404
        return Response(_srs_payload(request.user, slug))

    def post(self, request, slug):
        from jizz.models import CourseBirdResult, Species

        if slug not in COURSES:
            raise Http404
        birds = request.data.get('birds')
        if not isinstance(birds, dict) or len(birds) > MAX_SRS_ITEMS:
            return Response({'detail': f'Send birds as an object of up to {MAX_SRS_ITEMS}.'}, status=400)
        parsed = []
        for key, row in birds.items():
            try:
                sid_text, _, plumage = str(key).partition('|')
                sid = int(sid_text)
                box, right, wrong = int(row['box']), int(row.get('right', 0)), int(row.get('wrong', 0))
                due, seen = _parse_srs_time(row['due']), _parse_srs_time(row['seen'])
            except (KeyError, TypeError, ValueError):
                return Response({'detail': 'Each bird needs box, due and seen.'}, status=400)
            if not (0 <= box <= SRS_BOXES and 0 <= right <= 100000 and 0 <= wrong <= 100000 and len(plumage) <= 100):
                return Response({'detail': 'Bird out of range.'}, status=400)
            parsed.append((sid, plumage, box, due, seen, right, wrong))
        existing_species = set(Species.objects.filter(id__in={p[0] for p in parsed}).values_list('id', flat=True))
        current = {
            (r.species_id, r.plumage): r
            for r in CourseBirdResult.objects.filter(user=request.user, course=slug)
        }
        for sid, plumage, box, due, seen, right, wrong in parsed:
            if sid not in existing_species:
                continue
            row = current.get((sid, plumage))
            if row is None:
                CourseBirdResult.objects.create(
                    user=request.user, course=slug, species_id=sid, plumage=plumage,
                    box=box, due_at=due, last_seen=seen, right=right, wrong=wrong,
                )
            elif seen > row.last_seen:
                row.box, row.due_at, row.last_seen, row.right, row.wrong = box, due, seen, right, wrong
                row.save()
        return Response(_srs_payload(request.user, slug))
