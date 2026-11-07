"""Public, read-only course API. Progress is kept on the device for now."""

from django.core.cache import cache
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
