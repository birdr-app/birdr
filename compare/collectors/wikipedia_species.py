"""Fetch short Wikipedia species ID notes (CC BY-SA) into SpeciesFact."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote

from compare.facts import WIKIPEDIA_ATTRIBUTION, WIKIPEDIA_LICENSE, upsert_fact
from compare.models import SpeciesFact
from jizz.models import Species
from jizz.services.taxonomy_texts import WikipediaClient, first_sentences

logger = logging.getLogger(__name__)

# Generous ID excerpts; model must still paraphrase, not paste.
_MAX_INTRO_SENTENCES = 3
_MAX_ID_CHARS = 4000
_MAX_ID_PARAS = 12

# Prefer paragraphs that carry field-ID signal (EN + NL).
_ID_KEYWORDS = (
    'wing',
    'wings',
    'primaries',
    'secondaries',
    'coverts',
    'juvenile',
    'juveniles',
    'immature',
    'immatures',
    'first-winter',
    'first winter',
    'first-year',
    'plumage',
    'confused',
    'confusion',
    'similar',
    'pattern',
    'diagnostic',
    'triangle',
    'triangular',
    'w-shaped',
    'w band',
    'mantle',
    'tail',
    'bill',
    # Dutch
    'vleugel',
    'vleugelpatroon',
    'handpennen',
    'armpennen',
    'dekveren',
    'juveniel',
    'juvenielen',
    'onvolwassen',
    'eerste winter',
    'eerstejaars',
    'verenkleed',
    'verward',
    'verwarring',
    'patroon',
    'driehoek',
    'snavel',
    'staart',
)

_SECTION_HINTS = (
    'description',
    'identification',
    'plumage',
    'juvenile',
    'similar',
    'kenmerken',
    'herkenning',
    'uiterlijk',
    'juveniel',
)


def wikipedia_page_url(locale: str, title: str) -> str:
    return f'https://{locale}.wikipedia.org/wiki/{quote(title.replace(" ", "_"))}'


def extract_identification_notes(plain_text: str, *, max_chars: int = _MAX_ID_CHARS) -> str:
    """
    Pull short ID-relevant paragraphs from a plain-text Wikipedia page.

    Favours description / plumage / juvenile / similar-species material and
    sentences that mention wing pattern, age, or confusion species.
    """
    text = (plain_text or '').strip()
    if not text:
        return ''

    blocks = [b.strip() for b in re.split(r'\n{2,}|\n(?==)', text) if b.strip()]
    # Also split single newlines when the extract has no blank lines.
    if len(blocks) <= 2:
        blocks = [b.strip() for b in text.split('\n') if b.strip()]

    scored: list[tuple[int, str]] = []
    in_id_section = False

    def _as_heading(block: str) -> str | None:
        """Return lowercased heading text, or None if this is body copy."""
        heading_match = re.match(r'=+\s*(.+?)\s*=+\s*$', block)
        if heading_match:
            return heading_match.group(1).lower()
        # Plain extracts use short title lines without wiki markup.
        if len(block) <= 48 and not block.endswith(('.', '!', '?', ';')):
            lower = block.lower()
            if any(hint in lower for hint in _SECTION_HINTS):
                return lower
        return None

    for block in blocks:
        heading = _as_heading(block)
        if heading is not None:
            in_id_section = any(hint in heading for hint in _SECTION_HINTS)
            continue

        # Skip infobox-ish or tiny fragments.
        if len(block) < 60:
            continue
        lower = block.lower()
        score = 0
        if in_id_section:
            score += 3
        hits = sum(1 for key in _ID_KEYWORDS if key in lower)
        if hits:
            score += hits
        # Strong boost for age-specific wing marks (the common gull pitfall).
        if any(k in lower for k in ('wing', 'vleugel', 'primaries', 'handpennen')) and any(
            k in lower
            for k in (
                'juvenile',
                'juveniel',
                'immature',
                'onvolwassen',
                'first-winter',
                'first winter',
                'eerste winter',
                'pattern',
                'patroon',
                'confused',
                'verward',
            )
        ):
            score += 5
        if score > 0:
            scored.append((score, block))

    scored.sort(key=lambda row: (-row[0], -len(row[1])))
    chosen: list[str] = []
    total = 0
    for _score, block in scored[:_MAX_ID_PARAS]:
        piece = re.sub(r'\s+', ' ', block).strip()
        if not piece:
            continue
        if total + len(piece) > max_chars and chosen:
            remaining = max_chars - total
            if remaining > 120:
                chosen.append(piece[: remaining - 1].rstrip() + '…')
            break
        chosen.append(piece[:max_chars] if not chosen and len(piece) > max_chars else piece)
        total += len(chosen[-1])
        if total >= max_chars:
            break
    return '\n\n'.join(chosen).strip()


def ensure_wikipedia_species_facts(
    species: Species,
    *,
    client: WikipediaClient | None = None,
    locale: str = 'en',
) -> list[SpeciesFact]:
    """
    Store a short intro plus ID/plumage excerpts for the species Wikipedia page.

    Uses Latin name search; stores CC BY-SA excerpts under identification / plumage.
    """
    latin = (species.name_latin or '').strip()
    common = (species.name or '').strip()
    if not latin and not common:
        return []

    wiki = client or WikipediaClient()
    title = None
    intro = ''
    for query in (latin, common):
        if not query:
            continue
        found = wiki.search_title(locale, query)
        if not found:
            continue
        resolved, intro = wiki.page_intro(locale, found)
        title = resolved
        if intro.strip():
            break

    if not title or not (intro or '').strip():
        logger.info('No Wikipedia page for species %s (%s)', species.name, latin)
        return []

    url = wikipedia_page_url(locale, title)
    saved: list[SpeciesFact] = []

    text = first_sentences(intro, max_sentences=_MAX_INTRO_SENTENCES)
    if text:
        saved.append(
            upsert_fact(
                species,
                source=SpeciesFact.SOURCE_WIKIPEDIA,
                category='identification',
                key='intro',
                value_text=text,
                source_url=url,
                license=WIKIPEDIA_LICENSE,
                attribution=WIKIPEDIA_ATTRIBUTION,
            )
        )

    lower = intro.lower()
    if any(token in lower for token in ('habitat', 'breeds in', 'found in', 'inhabits')):
        saved.append(
            upsert_fact(
                species,
                source=SpeciesFact.SOURCE_WIKIPEDIA,
                category='habitat',
                key='intro',
                value_text=first_sentences(intro, max_sentences=2),
                source_url=url,
                license=WIKIPEDIA_LICENSE,
                attribution=WIKIPEDIA_ATTRIBUTION,
            )
        )

    # Full-page plain text for Description / Juvenile / Similar species excerpts.
    plain = wiki.page_plain_text(locale, title)
    id_notes = extract_identification_notes(plain)
    if id_notes:
        # Prefer plumage category when the excerpt is mostly about age/wing pattern.
        id_lower = id_notes.lower()
        category = (
            'plumage'
            if any(
                k in id_lower
                for k in (
                    'plumage',
                    'wing',
                    'juvenile',
                    'vleugel',
                    'juveniel',
                    'verenkleed',
                    'pattern',
                    'patroon',
                )
            )
            else 'identification'
        )
        key = 'field_id' if category == 'identification' else 'wing_plumage'
        saved.append(
            upsert_fact(
                species,
                source=SpeciesFact.SOURCE_WIKIPEDIA,
                category=category,
                key=key,
                value_text=id_notes,
                source_url=url,
                license=WIKIPEDIA_LICENSE,
                attribution=WIKIPEDIA_ATTRIBUTION,
            )
        )

    return saved
