from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from jizz.usage_analytics import (
    _filtered_queryset,
    default_date_range,
    parse_date_param,
    record_usage_event,
    usage_stats_payload,
    usage_top_ips,
)


class UsageEventCreateSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=500)
    event_type = serializers.CharField(max_length=20, required=False, default='page_view')
    platform = serializers.CharField(max_length=20, required=False, default='web')
    session_key = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    country_code = serializers.CharField(max_length=2, required=False, allow_blank=True, default='')
    referer = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    utm_source = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')
    utm_medium = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')
    utm_campaign = serializers.CharField(max_length=180, required=False, allow_blank=True, default='')
    metadata = serializers.JSONField(required=False, default=dict)


class UsageEventCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UsageEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        record_usage_event(
            request,
            path=data['path'],
            event_type=data.get('event_type', 'page_view'),
            platform=data.get('platform', 'web'),
            session_key=data.get('session_key', ''),
            country_code=data.get('country_code') or None,
            metadata=data.get('metadata') or {},
            referer=data.get('referer') or None,
            utm_source=data.get('utm_source') or '',
            utm_medium=data.get('utm_medium') or '',
            utm_campaign=data.get('utm_campaign') or '',
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _usage_query_params(request):
    default_start, default_end = default_date_range()
    start = parse_date_param(request.GET.get('start'), default_start)
    end = parse_date_param(request.GET.get('end'), default_end)
    platform = (request.GET.get('platform') or '').strip().lower() or None
    device_type = (request.GET.get('device_type') or '').strip().lower() or None
    country_code = (request.GET.get('country') or '').strip().upper() or None
    event_type = (request.GET.get('event_type') or '').strip().lower() or None
    ip_address = (request.GET.get('ip') or '').strip() or None
    return start, end, platform, device_type, country_code, event_type, ip_address


def _usage_filtered_qs(request):
    start, end, platform, device_type, country_code, event_type, ip_address = _usage_query_params(request)
    return start, end, platform, device_type, country_code, event_type, ip_address, _filtered_queryset(
        start,
        end,
        platform=platform,
        device_type=device_type,
        country_code=country_code,
        event_type=event_type,
        ip_address=ip_address,
    )


@staff_member_required
def staff_usage_view(request):
    start, end, platform, device_type, country_code, event_type, ip_address, qs = _usage_filtered_qs(request)
    payload = usage_stats_payload(
        start,
        end,
        platform=platform,
        device_type=device_type,
        country_code=country_code,
        event_type=event_type,
        ip_address=ip_address,
    )
    top_ips = usage_top_ips(qs)
    return render(
        request,
        'jizz/staff_usage.html',
        {
            'active_section': 'usage',
            'start': payload['start'],
            'end': payload['end'],
            'platform': payload['platform'],
            'device_type': payload['device_type'],
            'country_code': payload['country_code'],
            'event_type': payload['event_type'],
            'ip_address': ip_address or '',
            'chart_json': payload,
            'top_ips': top_ips,
        },
    )


@staff_member_required
def staff_usage_api_view(request):
    start, end, platform, device_type, country_code, event_type, ip_address = _usage_query_params(request)
    return JsonResponse(
        usage_stats_payload(
            start,
            end,
            platform=platform,
            device_type=device_type,
            country_code=country_code,
            event_type=event_type,
            ip_address=ip_address,
        )
    )
