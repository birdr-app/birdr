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

from jizz.courses.content import COURSES, LessonNotFound, course_payload, lesson_payload

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
