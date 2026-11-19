"""Sex, life-stage and season labels of photos: parsers for the image sources, and the rules for
writing them.

Order of trust, from most to least: a human label, the image source (iNaturalist, GBIF, Wikimedia
Commons), the AI label. A human label is never overwritten. One `MediaPlumage` row holds a photo's
labels; `source` is the weakest provenance in it ('ai' as soon as the AI filled any field).
"""
from __future__ import annotations

import html
import re
from typing import Dict, Iterable, Optional

from media.models import MediaPlumage

FIELDS = ('sex', 'stage', 'season')
SEX_VALUES = tuple(v for v, _ in MediaPlumage.SEX_CHOICES)
STAGE_VALUES = tuple(v for v, _ in MediaPlumage.STAGE_CHOICES)
SEASON_VALUES = tuple(v for v, _ in MediaPlumage.SEASON_CHOICES)
FIELD_VALUES = {'sex': SEX_VALUES, 'stage': STAGE_VALUES, 'season': SEASON_VALUES}
SOURCES_FROM_IMAGE_SOURCE = ('inaturalist', 'gbif', 'wikimedia')

# Source rows carry no confidence of their own; they count as this when a threshold is applied.
SOURCE_CONFIDENCE = 0.9

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

_SEASON = {
    'breeding': 'breeding', 'summer': 'breeding', 'nuptial': 'breeding', 'alternate': 'breeding',
    'non_breeding': 'non_breeding', 'non-breeding': 'non_breeding', 'nonbreeding': 'non_breeding',
    'winter': 'non_breeding', 'basic': 'non_breeding',
    'eclipse': 'eclipse',
}


def normalize_sex(value) -> str:
    return _SEX.get(str(value or '').strip().lower(), '')


def normalize_stage(value) -> str:
    return _STAGE.get(str(value or '').strip().lower(), '')


def normalize_season(value) -> str:
    return _SEASON.get(str(value or '').strip().lower().replace(' ', '_'), '')


# iNaturalist controlled terms (GET /v1/controlled_terms). Birds only have adult/juvenile.
# iNaturalist has no plumage-season term, so its labels never carry a season.
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
    """GBIF has sex and lifeStage, no season."""
    return {'sex': normalize_sex(occ.get('sex')), 'stage': normalize_stage(occ.get('lifeStage'))}


# --- Wikimedia Commons: file description and categories -------------------------------------
#
# Words are matched whole. A description that names both values of a field ("male and female",
# "adult feeding juvenile") says nothing about the one bird in the photo, so that field stays empty.

_W = r'(?<![\w])(?:%s)(?![\w])'


def _rx(words: str) -> 're.Pattern':
    return re.compile(_W % words, re.IGNORECASE)


_COMMONS_SEX = {
    'female': _rx(r'females?|♀|vrouwtjes?|weibchen|weiblich|femelles?|hembras?'),
    'male': _rx(r'males?|♂|mannetjes?|männchen|maennchen|männlich|mâles?|machos?'),
}
_COMMONS_STAGE = {
    'chick': _rx(r'chicks?|nestlings?|hatchlings?|pullus|kuikens?|küken|poussins?'),
    'juvenile': _rx(r'juveniles?|juvenil|juvéniles?|fledglings?|jeunes?'),
    'immature': _rx(
        r'immatures?|sub-?adults?|(?:first|second|third)[- ](?:winter|year|summer)|onvolwassen|'
        r'subadulte|unreif'
    ),
    'adult': _rx(r'adults?|volwassen|adultes?|erwachsen'),
}
_NON_BREEDING = re.compile(
    r'non[- ]?breeding|(?<![\w])winter[- ](?:plumage|dress)(?![\w])|'
    r'(?<![\w])(?:adult|male|female|immature)s?[ ]winter(?![\w])|(?<![\w])basic[ ]plumage(?![\w])|'
    r'winterkleed|schlichtkleid|plumage hivernal',
    re.IGNORECASE,
)
_BREEDING = re.compile(
    r'(?<![\w])breeding[ ](?:plumage|dress|male|female|adult)(?![\w])|'
    r'(?<![\w])(?:summer|nuptial|alternate)[ ](?:plumage|dress)(?![\w])|'
    r'(?<![\w])(?:adult|male|female)s?[ ](?:summer|breeding)(?![\w])|'
    r'zomerkleed|prachtkleed|prachtgewand|plumage nuptial',
    re.IGNORECASE,
)
_ECLIPSE = re.compile(r'(?<![\w])eclipse(?![\w])', re.IGNORECASE)


def _one(text: str, patterns: Dict[str, 're.Pattern']) -> str:
    hits = [value for value, rx in patterns.items() if rx.search(text)]
    return hits[0] if len(hits) == 1 else ''


def from_commons_text(*parts: str) -> Dict[str, str]:
    """Sex, stage and season from the title, description and category names of a Commons file.

    Anything between `<` and `>` is dropped and HTML entities are decoded, so the HTML of an
    ``ImageDescription`` can be passed as it is.
    """
    text = ' \n '.join(html.unescape(re.sub(r'<[^>]+>', ' ', p or '')) for p in parts).replace('_', ' ')
    seasons = set()
    if _NON_BREEDING.search(text):
        seasons.add('non_breeding')
    # "non-breeding plumage" must not also read as "breeding plumage"
    if _BREEDING.search(_NON_BREEDING.sub(' ', text)):
        seasons.add('breeding')
    if _ECLIPSE.search(text):
        seasons.add('eclipse')
    return {
        'sex': _one(text, _COMMONS_SEX),
        'stage': _one(text, _COMMONS_STAGE),
        'season': next(iter(seasons)) if len(seasons) == 1 else '',
    }


def from_commons_extmetadata(meta: Optional[Dict]) -> Dict[str, str]:
    """Labels from the `extmetadata` of a Commons `imageinfo` (description, object name, categories)."""
    meta = meta or {}

    def value(key):
        return (meta.get(key) or {}).get('value') or ''

    categories = value('Categories').replace('|', ' \n ')
    return from_commons_text(value('ObjectName'), value('ImageDescription'), categories)


# --- Writing -------------------------------------------------------------------------------


def effective_confidence(plumage: MediaPlumage) -> float:
    """How far a stored label can be trusted: human 1, AI its own confidence, a source `SOURCE_CONFIDENCE`."""
    if plumage.source == 'human':
        return 1.0
    if plumage.confidence is not None:
        return float(plumage.confidence)
    return SOURCE_CONFIDENCE


def save_source_plumage(media, source: str, labels: Dict[str, str], dry_run: bool = False) -> bool:
    """Store labels from an image source. True when a row was created or changed.

    Never touches a human label. Fields the source gives replace what is stored (the source is
    more reliable than an AI label, and newer than an older source); fields it does not give are
    kept. A row the AI contributed to stays 'ai', so its confidence still applies.
    """
    new = {f: labels.get(f, '') for f in FIELDS}
    if not any(new.values()):
        return False
    existing = MediaPlumage.objects.filter(media=media).first()
    if existing is None:
        if not dry_run:
            MediaPlumage.objects.create(media=media, source=source, **new)
        return True
    if existing.source == 'human':
        return False
    changes = {f: v for f, v in new.items() if v and getattr(existing, f) != v}
    if not changes:
        return False
    if not dry_run:
        for f, v in changes.items():
            setattr(existing, f, v)
        if existing.source != 'ai':
            existing.source = source
        existing.save()
    return True


def apply_ai_label(media, label: Dict, model_version: str, min_confidence: float = 0.0,
                   dry_run: bool = False) -> str:
    """Store an AI label ({sex, stage, season, confidence}; '' or 'unknown' = not visible).

    Returns 'human' (untouched), 'created', 'filled', 'unchanged' or 'low_confidence'. Only empty
    fields of a source row are filled; the AI's own earlier values are replaced. A low-confidence
    answer writes no labels but records that the photo was asked (`model_version`), so the next run
    does not pay for it again. Never touches a human row.
    """
    confidence = max(0.0, min(1.0, float(label.get('confidence') or 0.0)))
    low = confidence < min_confidence
    new = {f: ('' if low else label.get(f) or '') for f in FIELDS}
    new = {f: (v if v in FIELD_VALUES[f] else '') for f, v in new.items()}
    existing = MediaPlumage.objects.filter(media=media).first()
    if existing is None:
        if not dry_run:
            MediaPlumage.objects.create(
                media=media, source='ai', confidence=confidence, model_version=model_version, **new,
            )
        return 'low_confidence' if low else 'created'
    if existing.source == 'human':
        return 'human'
    was_ai = existing.source == 'ai'
    filled = {f: v for f, v in new.items() if v and (was_ai or not getattr(existing, f))}
    if not dry_run:
        for f, v in filled.items():
            setattr(existing, f, v)
        existing.model_version = model_version
        if filled:
            existing.source = 'ai'
            existing.confidence = confidence
        existing.save()
    if low:
        return 'low_confidence'
    return 'filled' if filled else 'unchanged'


def set_human_plumage(media, **fields) -> MediaPlumage:
    """A person's confirmation or correction. Fields not given keep their value ('' clears one)."""
    row = MediaPlumage.objects.filter(media=media).first() or MediaPlumage(media=media)
    for f in FIELDS:
        if f in fields:
            setattr(row, f, fields[f] or '')
    row.source, row.confidence, row.model_version = 'human', 1.0, ''
    row.save()
    return row
