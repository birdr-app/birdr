"""Sex and life-stage labels taken from source metadata (iNaturalist, GBIF)."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from media.models import MediaPlumage

_SEX = {
    'male': 'male', 'm': 'male',
    'female': 'female', 'f': 'female',
}

_STAGE = {
    'adult': 'adult',
    'subadult': 'immature', 'sub-adult': 'immature', 'immature': 'immature',
    'juvenile': 'juvenile', 'fledgling': 'juvenile', 'fledgeling': 'juvenile',
    'nestling': 'chick', 'chick': 'chick', 'hatchling': 'chick',
}


def normalize_sex(value) -> str:
    return _SEX.get(str(value or '').strip().lower(), '')


def normalize_stage(value) -> str:
    return _STAGE.get(str(value or '').strip().lower(), '')


# iNaturalist controlled terms (GET /v1/controlled_terms). Birds only have adult/juvenile.
INAT_LIFE_STAGE, INAT_SEX = 1, 9
_INAT_STAGE_VALUES = {2: 'adult', 8: 'juvenile'}
_INAT_SEX_VALUES = {10: 'female', 11: 'male'}


def _inat_rejected(ann: Dict) -> bool:
    """Community voted the annotation down (v2 gives vote_score, v1 a votes list)."""
    if (ann.get('vote_score') or 0) < 0:
        return True
    votes = ann.get('votes') or []
    up = sum(1 for v in votes if v.get('vote_flag'))
    return len(votes) - up > up


def from_inat_annotations(annotations: Optional[Iterable[Dict]]) -> Dict[str, str]:
    """Sex and stage from an iNaturalist observation's annotations (term ids, or labels)."""
    out = {'sex': '', 'stage': ''}
    for ann in annotations or []:
        if _inat_rejected(ann):
            continue
        attr_id = ann.get('controlled_attribute_id')
        value_id = ann.get('controlled_value_id')
        if attr_id is None:
            attr_id = (ann.get('controlled_attribute') or {}).get('id')
            value_id = (ann.get('controlled_value') or {}).get('id')
        if attr_id == INAT_SEX:
            out['sex'] = out['sex'] or _INAT_SEX_VALUES.get(value_id, '')
        elif attr_id == INAT_LIFE_STAGE:
            out['stage'] = out['stage'] or _INAT_STAGE_VALUES.get(value_id, '')
    return out


def from_gbif_occurrence(occ: Dict) -> Dict[str, str]:
    return {'sex': normalize_sex(occ.get('sex')), 'stage': normalize_stage(occ.get('lifeStage'))}


def save_source_plumage(media, source: str, labels: Dict[str, str]) -> bool:
    """Store source labels unless there are none or a human/AI label already exists."""
    sex, stage = labels.get('sex', ''), labels.get('stage', '')
    if not (sex or stage):
        return False
    existing = MediaPlumage.objects.filter(media=media).first()
    if existing and existing.source in ('human', 'ai'):
        return False
    MediaPlumage.objects.update_or_create(
        media=media, defaults={'sex': sex, 'stage': stage, 'source': source},
    )
    return True
