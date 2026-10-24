"""Find and act on non-photo Wikimedia images (see ``media.non_photo``).

Clear cases get a rejected review from the ``birdr-auto-review`` account, which
hides them from games via ``sync_media_hide``. Unclear cases get a flag from the
same account so staff can look. Media a person already approved is left alone.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from media.models import FlagMedia, Media, MediaReview
from media.non_photo import CLEAR, classify

AUTO_REVIEW_USERNAME = 'birdr-auto-review'
AUTO_REVIEW_NAME = 'Birdr auto review'


@dataclass
class SweepReport:
    scanned: int = 0
    counts: dict = field(default_factory=lambda: defaultdict(int))
    samples: dict = field(default_factory=lambda: defaultdict(list))
    skipped_approved: int = 0
    already_done: int = 0
    rejected: int = 0
    flagged: int = 0
    clear_ids: list = field(default_factory=list)
    unclear_ids: list = field(default_factory=list)
    reasons: dict = field(default_factory=dict)

    def total(self, kind: str) -> int:
        return sum(n for (k, _reason), n in self.counts.items() if k == kind)


def auto_reviewer():
    """The inactive user (and its player) that signs automatic reviews and flags."""
    from jizz.models import Player

    user, _ = get_user_model().objects.get_or_create(
        username=AUTO_REVIEW_USERNAME,
        defaults={'is_active': False, 'first_name': AUTO_REVIEW_NAME},
    )
    player = Player.objects.filter(user=user).first() or Player.objects.create(
        user=user, name=AUTO_REVIEW_NAME, language='en',
    )
    return user, player


def wikimedia_images():
    """Visible Wikimedia images (hidden ones are already out of games)."""
    return Media.objects.filter(type='image', url__icontains='wikimedia', hide=False)


def scan(queryset=None, samples_per_reason: int = 5) -> SweepReport:
    report = SweepReport()
    queryset = wikimedia_images() if queryset is None else queryset
    approved = MediaReview.objects.filter(media=OuterRef('pk'), review_type=MediaReview.APPROVED).exclude(
        user__username=AUTO_REVIEW_USERNAME
    )
    rows = queryset.annotate(_approved=Exists(approved)).values_list('id', 'url', '_approved')
    for media_id, url, human_approved in rows.iterator(chunk_size=5000):
        report.scanned += 1
        result = classify(url or '')
        if result is None:
            continue
        kind, reason = result
        if human_approved:
            report.skipped_approved += 1
            continue
        report.counts[(kind, reason)] += 1
        if len(report.samples[(kind, reason)]) < samples_per_reason:
            report.samples[(kind, reason)].append((media_id, url))
        (report.clear_ids if kind == CLEAR else report.unclear_ids).append(media_id)
        report.reasons[media_id] = reason
    return report


def apply(report: SweepReport, batch_size: int = 1000) -> SweepReport:
    user, player = auto_reviewer()
    for start in range(0, len(report.clear_ids), batch_size):
        ids = report.clear_ids[start:start + batch_size]
        with transaction.atomic():
            done = set(
                MediaReview.objects.filter(media_id__in=ids, user=user).values_list('media_id', flat=True)
            )
            reasons = {media_id: report.reasons[media_id] for media_id in ids if media_id not in done}
            MediaReview.objects.bulk_create([
                MediaReview(
                    media_id=media_id, user=user, review_type=MediaReview.REJECTED,
                    description=f'Automatic: not a bird photo ({reason})',
                )
                for media_id, reason in reasons.items()
            ])
            # bulk_create skips MediaReview.save(), which normally syncs Media.hide.
            Media.objects.filter(id__in=reasons).update(hide=True)
            report.rejected += len(reasons)
            report.already_done += len(done)
    for start in range(0, len(report.unclear_ids), batch_size):
        ids = report.unclear_ids[start:start + batch_size]
        before = FlagMedia.objects.filter(media_id__in=ids, player=player).count()
        FlagMedia.objects.bulk_create(
            [
                FlagMedia(media_id=media_id, player=player,
                          description=f'Automatic: check whether this is a bird photo ({report.reasons[media_id]})')
                for media_id in ids
            ],
            ignore_conflicts=True,
        )
        report.flagged += FlagMedia.objects.filter(media_id__in=ids, player=player).count() - before
    return report


def exclude_auto_reviewer(queryset):
    """Leave the automatic account out of reviewer statistics."""
    return queryset.exclude(Q(user__username=AUTO_REVIEW_USERNAME) | Q(player__user__username=AUTO_REVIEW_USERNAME))
