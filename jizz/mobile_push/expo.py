"""
Expo Push API helpers.

Tickets returned by /push/send and receipts from /push/getReceipts are both
checked for ``DeviceNotRegistered``; the matching token is then disabled
(PushDevice) or removed (legacy DeviceToken) so we stop sending to it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from django.conf import settings

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
EXPO_RECEIPTS_URL = 'https://exp.host/--/api/v2/push/getReceipts'
ANDROID_CHANNEL_ID = 'default'
SEND_CHUNK_SIZE = 100
RECEIPT_CHUNK_SIZE = 1000


@dataclass
class PushResult:
    """Outcome of one or more Expo sends. Truthy when at least one ticket was ok."""

    sent: int = 0
    failed: int = 0
    disabled: int = 0
    skipped: bool = False
    # ticket id -> token, for fetch_receipts()
    tickets: dict[str, str] = field(default_factory=dict)
    # token -> 'ok' or error code/message
    per_token: dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.sent > 0

    def merge(self, other: 'PushResult') -> 'PushResult':
        self.sent += other.sent
        self.failed += other.failed
        self.disabled += other.disabled
        self.skipped = self.skipped or other.skipped
        self.tickets.update(other.tickets)
        self.per_token.update(other.per_token)
        return self


@dataclass
class ReceiptResult:
    ok: int = 0
    failed: int = 0
    disabled: int = 0
    pending: int = 0


def build_message(
    expo_push_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        'to': expo_push_token.strip(),
        'title': title,
        'body': body,
        'data': data or {},
        'sound': 'default',
        'priority': 'high',
        'channelId': ANDROID_CHANNEL_ID,
    }


def disable_push_token(token: str) -> int:
    """Stop sending to a token Expo reported as DeviceNotRegistered."""
    from jizz.models import DeviceToken, PushDevice

    updated = PushDevice.objects.filter(expo_push_token=token, enabled=True).update(enabled=False)
    deleted, _ = DeviceToken.objects.filter(token=token).delete()
    if updated or deleted:
        logger.info('Disabled unregistered push token %s', token[:40])
    return updated + deleted


def _headers() -> dict[str, str]:
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    access_token = getattr(settings, 'EXPO_ACCESS_TOKEN', '')
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
    return headers


def _error_code(item: dict[str, Any]) -> str:
    details = item.get('details') or {}
    return details.get('error') or item.get('message') or 'unknown_error'


def _send_chunk(messages: list[dict[str, Any]]) -> PushResult:
    import requests

    result = PushResult()
    tokens = [m['to'] for m in messages]
    url = getattr(settings, 'EXPO_PUSH_URL', EXPO_PUSH_URL)
    try:
        resp = requests.post(url, json=messages, headers=_headers(), timeout=10)
    except Exception as exc:
        logger.warning('Expo push request failed: %s', exc)
        result.failed = len(messages)
        result.per_token = {t: f'request_failed: {exc}' for t in tokens}
        return result

    if resp.status_code != 200:
        logger.warning('Expo push failed: %s %s', resp.status_code, resp.text[:500])
        result.failed = len(messages)
        result.per_token = {t: f'http_{resp.status_code}' for t in tokens}
        return result

    try:
        tickets = resp.json().get('data') or []
    except Exception:
        tickets = []
    if isinstance(tickets, dict):
        # Expo returns a single object when a single (non-list) message is sent.
        tickets = [tickets]

    for index, token in enumerate(tokens):
        ticket = tickets[index] if index < len(tickets) else None
        if not ticket:
            result.failed += 1
            result.per_token[token] = 'missing_ticket'
            continue
        if ticket.get('status') == 'ok':
            result.sent += 1
            result.per_token[token] = 'ok'
            if ticket.get('id'):
                result.tickets[ticket['id']] = token
            continue
        code = _error_code(ticket)
        result.failed += 1
        result.per_token[token] = code
        logger.warning('Expo push ticket error for %s: %s', token[:40], ticket.get('message', code))
        if code == 'DeviceNotRegistered':
            if disable_push_token(token):
                result.disabled += 1
    return result


def send_expo_push_many(
    tokens: Iterable[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> PushResult:
    """Send the same notification to many tokens (chunked). Never raises."""
    clean = []
    for token in tokens:
        token = (token or '').strip()
        if token and token not in clean:
            clean.append(token)
    result = PushResult()
    if not clean:
        return result

    if not getattr(settings, 'SEND_PUSH_NOTIFICATIONS', False):
        logger.info('Expo push skipped (SEND_PUSH_NOTIFICATIONS=False): %s', title)
        result.skipped = True
        result.per_token = {t: 'skipped' for t in clean}
        return result

    messages = [build_message(t, title, body, data) for t in clean]
    for start in range(0, len(messages), SEND_CHUNK_SIZE):
        result.merge(_send_chunk(messages[start:start + SEND_CHUNK_SIZE]))
    return result


def send_expo_push(
    expo_push_token: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> PushResult:
    """
    Send one push via Expo. The result is truthy when Expo accepted it.
    Does not raise; logs errors.
    """
    if not expo_push_token or not expo_push_token.strip():
        logger.warning('send_expo_push: missing token')
        return PushResult()
    return send_expo_push_many([expo_push_token], title, body, data=data)


def fetch_receipts(
    ticket_ids: Iterable[str] | dict[str, str],
) -> ReceiptResult:
    """
    Look up delivery receipts for tickets (call ~15+ minutes after sending).

    Pass ``PushResult.tickets`` (ticket id -> token) so DeviceNotRegistered
    receipts can disable the right token; a plain list of ids also works when
    Expo includes ``details.expoPushToken`` in the receipt.
    """
    token_by_ticket = dict(ticket_ids) if isinstance(ticket_ids, dict) else {i: '' for i in ticket_ids}
    ids = [i for i in token_by_ticket if i]
    result = ReceiptResult()
    if not ids or not getattr(settings, 'SEND_PUSH_NOTIFICATIONS', False):
        return result

    import requests

    url = getattr(settings, 'EXPO_RECEIPTS_URL', EXPO_RECEIPTS_URL)
    for start in range(0, len(ids), RECEIPT_CHUNK_SIZE):
        chunk = ids[start:start + RECEIPT_CHUNK_SIZE]
        try:
            resp = requests.post(url, json={'ids': chunk}, headers=_headers(), timeout=10)
            receipts = (resp.json().get('data') or {}) if resp.status_code == 200 else None
        except Exception as exc:
            logger.warning('Expo receipts request failed: %s', exc)
            receipts = None
        if receipts is None:
            result.pending += len(chunk)
            continue
        for ticket_id in chunk:
            receipt = receipts.get(ticket_id)
            if not receipt:
                result.pending += 1
                continue
            if receipt.get('status') == 'ok':
                result.ok += 1
                continue
            result.failed += 1
            code = _error_code(receipt)
            logger.warning('Expo push receipt error %s: %s', ticket_id, receipt.get('message', code))
            if code == 'DeviceNotRegistered':
                token = token_by_ticket.get(ticket_id) or (receipt.get('details') or {}).get('expoPushToken')
                if token and disable_push_token(token):
                    result.disabled += 1
    return result
