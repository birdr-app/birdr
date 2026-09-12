"""
AI service for generating species comparisons using OpenAI.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class ComparisonGenerationError(Exception):
    """Raised when a comparison cannot be generated."""


def _exception_text(exc: BaseException) -> str:
    parts = [str(exc)]
    cause = getattr(exc, '__cause__', None)
    if cause is not None:
        parts.append(str(cause))
    return ' '.join(parts).lower()


def _is_quota_error(exc: BaseException) -> bool:
    text = _exception_text(exc)
    return any(
        token in text
        for token in (
            'insufficient_quota',
            'credit_balance_exhausted',
            'no credits remaining',
            'exceeded your current quota',
            'out of credits',
        )
    )


def _friendly_openai_error(exc: BaseException) -> str:
    text = _exception_text(exc)
    if _is_quota_error(exc):
        return (
            'The AI comparison service is out of credits right now. '
            'You can still write a better description if you are logged in.'
        )
    if 'rate limit' in text or '429' in text:
        return 'The AI comparison service is busy. Please try again in a moment.'
    return 'Could not generate the comparison. Please try again.'

PROMPT_VERSION = 'v3'
DEFAULT_MODEL = 'gpt-4o'
HANDBOOK_MODEL = 'botw-extract'
GROUNDING_CATEGORIES = ('identification', 'similar_species')
NO_GROUNDING_MESSAGE = (
    'A handbook comparison is not available for this pair yet '
    '(no Birds of the World identification notes). '
    'You can still write a better description if you are logged in.'
)

# First tokens that match too many unrelated passages in Birds of the World text.
_GENERIC_NAME_TOKENS = frozenset({
    'american', 'arctic', 'atlantic', 'black', 'blue', 'brown', 'common',
    'desert', 'eastern', 'eurasian', 'european', 'great', 'greater', 'green',
    'grey', 'gray', 'house', 'indian', 'lesser', 'little', 'long', 'marsh',
    'northern', 'pacific', 'red', 'reed', 'rock', 'sand', 'sea', 'short',
    'southern', 'steppe', 'tree', 'water', 'western', 'white', 'wood',
    'yellow',
})

# Only diagnostic handbook sections go into the prompt (not diet/range essays).
_TRAIT_ORDER = (
    'similar_species',
    'identification',
    'measurements',
    'vocalization',
    'plumage',
    'size',
)

_TRAIT_CHAR_LIMITS = {
    'similar_species': 12000,
    'identification': 5000,
    'measurements': 1400,
    'vocalization': 1400,
    'plumage': 800,
    'size': 800,
}

_JSON_KEYS = (
    'summary',
    'size_comparison',
    'plumage_comparison',
    'behavior_comparison',
    'habitat_comparison',
    'vocalization_comparison',
    'identification_tips',
)

SYSTEM_PROMPT = (
    'You are a field-guide editor for Birdr, writing for birdwatchers who need '
    'to tell two similar species apart in the field. Be precise, practical and '
    'honest about uncertainty. Prefer diagnostic, observable differences over '
    'encyclopedic lists. Only contrast these two species. Do not invent '
    'measurements, ranges, songs or field marks that are not in the notes. '
    'If sources conflict, prefer Birds of the World similar-species passages. '
    'Leave a section empty when it is not diagnostic. Reply with a JSON object only.'
)


def comparison_model_name() -> str:
    return (getattr(settings, 'COMPARISON_AI_MODEL', None) or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def comparison_prompt_version() -> str:
    return (getattr(settings, 'COMPARISON_AI_PROMPT_VERSION', None) or PROMPT_VERSION).strip() or PROMPT_VERSION


def has_grounding_traits(traits: dict | None) -> bool:
    """True when handbook identification or similar-species text is present."""
    for key in GROUNDING_CATEGORIES:
        if _trait_content((traits or {}).get(key)).strip():
            return True
    return False


def name_search_terms(name: str, latin_name: str | None = None) -> list[str]:
    """Tokens worth searching for in Birds of the World text."""
    terms: list[str] = []
    seen: set[str] = set()

    def add(value: str | None):
        token = (value or '').strip()
        if not token:
            return
        key = token.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(token)

    add(name)
    parts = [p for p in (name or '').split() if p]
    if len(parts) >= 2:
        add(' '.join(parts[:2]))
    if parts:
        first = re.sub(r"[^\w']", '', parts[0]).lower()
        if first and first not in _GENERIC_NAME_TOKENS and len(first) >= 5:
            add(parts[0])

    if latin_name:
        add(latin_name)
        latin_parts = latin_name.split()
        if latin_parts:
            genus = latin_parts[0]
            add(genus)
            if len(latin_parts) > 1:
                epithet = latin_parts[1]
                add(epithet)
                initial = genus[0]
                add(f'{initial}. {epithet}')
                add(f'{initial} {epithet}')

    return terms


def _clip(text: str, limit: int) -> str:
    value = (text or '').strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(' ', 1)[0] + '…'


def _trait_content(section_data) -> str:
    if isinstance(section_data, dict):
        return section_data.get('content') or ''
    if isinstance(section_data, str):
        return section_data
    return ''


class AIComparisonService:
    """Generate structured comparison texts with OpenAI."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
        self.model = model or comparison_model_name()
        self.prompt_version = comparison_prompt_version()
        if not self.api_key:
            logger.warning('OPENAI_API_KEY is not set; species comparisons cannot be generated')

    def _call_openai(self, prompt: str, max_tokens: int = 2000, *, json_object: bool = False) -> Optional[str]:
        if not self.api_key:
            raise ComparisonGenerationError(
                'Comparisons cannot be generated because the AI service is not configured.'
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            logger.exception('openai package is not installed')
            raise ComparisonGenerationError(
                'Comparisons cannot be generated because the AI library is missing.'
            ) from exc

        try:
            client = OpenAI(api_key=self.api_key, timeout=90.0)
            kwargs: Dict[str, Any] = {
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.3,
                'max_tokens': max_tokens,
            }
            if json_object:
                kwargs['response_format'] = {'type': 'json_object'}
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ''
            return content.strip() or None
        except Exception as exc:
            logger.exception('OpenAI comparison request failed (model=%s)', self.model)
            raise ComparisonGenerationError(_friendly_openai_error(exc)) from exc

    def generate_species_comparison(
        self,
        species_1_traits: Dict,
        species_2_traits: Dict,
        species_1_name: str,
        species_2_name: str,
        species_1_latin: str | None = None,
        species_2_latin: str | None = None,
    ) -> Dict[str, str]:
        latin_1 = species_1_latin or species_1_traits.get('name_latin') or None
        latin_2 = species_2_latin or species_2_traits.get('name_latin') or None
        if not has_grounding_traits(species_1_traits) and not has_grounding_traits(species_2_traits):
            raise ComparisonGenerationError(NO_GROUNDING_MESSAGE)

        similar_species_info = self._extract_similar_species_mentions(
            species_1_traits,
            species_2_traits,
            species_1_name,
            species_2_name,
            latin_1,
            latin_2,
        )
        prompt = self._build_comparison_prompt(
            species_1_traits,
            species_2_traits,
            species_1_name,
            species_2_name,
            similar_species_info,
            latin_1,
            latin_2,
        )
        logger.info(
            'Generating %s vs %s comparison (%s, prompt %s chars)',
            species_1_name,
            species_2_name,
            self.model,
            len(prompt),
        )

        raw = self._call_openai(prompt, max_tokens=3500, json_object=True)

        if not raw:
            raise ComparisonGenerationError(
                'The comparison model returned an empty response. Please try again.'
            )

        parsed = self._parse_json_response(raw)
        if not parsed.get('summary'):
            parsed = self._parse_comparison_response(raw, species_1_name, species_2_name)
        if not parsed.get('summary'):
            raise ComparisonGenerationError(
                'The comparison model returned an empty response. Please try again.'
            )

        parsed['detailed_comparison'] = self._assemble_detailed(parsed)
        return parsed

    def _extract_similar_species_mentions(
        self,
        species_1_traits: Dict,
        species_2_traits: Dict,
        species_1_name: str,
        species_2_name: str,
        species_1_latin: str = None,
        species_2_latin: str = None,
    ) -> Dict[str, List]:
        result = {
            'species_1_mentions_species_2': [],
            'species_2_mentions_species_1': [],
        }

        def search_content(content, variations, section_name):
            mentions = []
            if not content:
                return mentions
            content_str = content if isinstance(content, str) else str(content)
            for variation in variations:
                escaped = re.escape(variation).replace(r'\ ', r'[\s.]+')
                pattern = r'(?<!\w)' + escaped + r'(?!\w)'
                match = re.search(pattern, content_str, re.IGNORECASE)
                if not match:
                    continue
                window = 3000 if section_name == 'similar_species' else 800
                start = max(0, match.start() - window)
                end = min(len(content_str), match.end() + window)
                mentions.append({
                    'section': section_name,
                    'matched_variation': variation,
                    'context': content_str[start:end].strip(),
                })
                break
            return mentions

        terms_2 = name_search_terms(species_2_name, species_2_latin)
        terms_1 = name_search_terms(species_1_name, species_1_latin)

        for section_name, section_data in species_1_traits.items():
            if section_name == 'name_latin':
                continue
            content = _trait_content(section_data)
            if content:
                result['species_1_mentions_species_2'].extend(
                    search_content(content, terms_2, section_name)
                )

        for section_name, section_data in species_2_traits.items():
            if section_name == 'name_latin':
                continue
            content = _trait_content(section_data)
            if content:
                result['species_2_mentions_species_1'].extend(
                    search_content(content, terms_1, section_name)
                )

        return result

    def _handbook_extract(
        self,
        species_1_traits: Dict,
        species_2_traits: Dict,
        species_1_name: str,
        species_2_name: str,
        similar_species_info: Dict | None = None,
    ) -> Dict[str, str]:
        """Assemble a comparison from BotW notes when the chat model is unavailable."""
        parsed = {key: '' for key in _JSON_KEYS}
        info = similar_species_info or {}
        mention_bits = []
        for source_name, mentions, other_name in (
            (species_1_name, info.get('species_1_mentions_species_2') or [], species_2_name),
            (species_2_name, info.get('species_2_mentions_species_1') or [], species_1_name),
        ):
            for mention in mentions:
                context = (mention.get('context') or '').strip()
                if not context:
                    continue
                mention_bits.append(f'**{source_name}** on {other_name}: {context}')

        tip_parts = []
        if mention_bits:
            tip_parts.append(
                '### Pairwise notes from Birds of the World\n\n'
                + '\n\n'.join(f'- {bit}' for bit in mention_bits)
            )
        for name, traits in (
            (species_1_name, species_1_traits),
            (species_2_name, species_2_traits),
        ):
            similar = _clip(_trait_content(traits.get('similar_species')), 2500)
            ident = _clip(_trait_content(traits.get('identification')), 1800)
            species_bits = []
            if similar:
                species_bits.append(f'**Similar species:** {similar}')
            if ident:
                species_bits.append(f'**Identification:** {ident}')
            if species_bits:
                tip_parts.append(f'### {name}\n\n' + '\n\n'.join(species_bits))
        parsed['identification_tips'] = '\n\n'.join(tip_parts)

        if mention_bits:
            lead = re.sub(r'\*\*[^*]+\*\*', '', mention_bits[0]).strip(' :')
            parsed['summary'] = _clip(
                f'{species_1_name} and {species_2_name} are compared from Birds of the World '
                f'similar-species and identification notes. {lead}',
                500,
            )
        else:
            parsed['summary'] = (
                f'{species_1_name} and {species_2_name} can be separated using the Birds of the World '
                f'identification notes below. This is a handbook extract, not a rewritten field-guide card.'
            )

        for dest, category in (
            ('size_comparison', 'measurements'),
            ('plumage_comparison', 'plumage'),
            ('vocalization_comparison', 'vocalization'),
        ):
            first = _clip(_trait_content(species_1_traits.get(category)), 700)
            second = _clip(_trait_content(species_2_traits.get(category)), 700)
            if not first and not second:
                continue
            chunks = []
            if first:
                chunks.append(f'**{species_1_name}:** {first}')
            if second:
                chunks.append(f'**{species_2_name}:** {second}')
            parsed[dest] = '\n\n'.join(chunks)
        return parsed

    def _format_traits(self, traits_dict: Dict) -> str:
        chunks = []
        for category in _TRAIT_ORDER:
            content = _clip(
                _trait_content(traits_dict.get(category)),
                _TRAIT_CHAR_LIMITS.get(category, 900),
            )
            if not content:
                continue
            chunks.append(f'{category.upper().replace("_", " ")}:\n{content}')
        return '\n\n'.join(chunks) if chunks else '(No extracted handbook notes for this species.)'

    def _build_comparison_prompt(
        self,
        species_1_traits: Dict,
        species_2_traits: Dict,
        species_1_name: str,
        species_2_name: str,
        similar_species_info: Dict = None,
        species_1_latin: str | None = None,
        species_2_latin: str | None = None,
    ) -> str:
        label_1 = species_1_name + (f' ({species_1_latin})' if species_1_latin else '')
        label_2 = species_2_name + (f' ({species_2_latin})' if species_2_latin else '')
        species_1_text = self._format_traits(species_1_traits)
        species_2_text = self._format_traits(species_2_traits)

        expert_bits = []
        seen_expert = set()
        if similar_species_info:
            for source_name, mentions, other_name in (
                (species_1_name, similar_species_info.get('species_1_mentions_species_2') or [], species_2_name),
                (species_2_name, similar_species_info.get('species_2_mentions_species_1') or [], species_1_name),
            ):
                for mention in mentions:
                    section = mention.get('section') or 'Unknown'
                    key = (source_name, section, mention.get('matched_variation') or '')
                    if key in seen_expert:
                        continue
                    seen_expert.add(key)
                    expert_bits.append(
                        f'{source_name} · {section.replace("_", " ")} mentions {other_name} '
                        f'(matched “{mention.get("matched_variation") or ""}”):\n'
                        f'{mention.get("context") or ""}'
                    )

        expert_block = ''
        if expert_bits:
            expert_block = (
                '\n\nEXPERT CROSS-MENTIONS FROM BIRDS OF THE WORLD (highest priority):\n'
                + '\n\n---\n\n'.join(expert_bits)
            )

        return f"""Compare these two species for a birdwatcher who has just mixed them up in a quiz.

SPECIES A: {label_1}
{species_1_text}

SPECIES B: {label_2}
{species_2_text}
{expert_block}

Write for someone with binoculars, not a monograph. Only contrast these two species. Lead with the most reliable field mark in the summary. If they are close relatives, compare structure first (bill, primary projection / wing formula, tail length, supercilium shape) before colour tone — colour is often the least reliable mark. Then cover song and call when the notes show they differ. If a feature is similar, say so in one clause and move on.

Do not invent measurements, songs, ranges or field marks. If the notes do not support a section, leave that JSON value empty — do not pad with generic natural history.

Identification tips should be ordered checks (most reliable first), including season, age or sex pitfalls when the sources mention them. You may cite Birds of the World once when using those expert passages. Do not use headings like "AI Field Diagnostics".

Return a JSON object with these string keys (markdown allowed inside strings: bold field marks, short lists):
- summary: 2–3 sentences
- size_comparison
- plumage_comparison
- behavior_comparison
- habitat_comparison
- vocalization_comparison
- identification_tips
Empty strings are allowed and preferred when a section is not diagnostic."""

    def _parse_json_response(self, response: str) -> Dict[str, str]:
        text = (response or '').strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if not match:
                return {}
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        if not isinstance(data, dict):
            return {}
        parsed = {key: '' for key in _JSON_KEYS}
        for key in _JSON_KEYS:
            value = data.get(key)
            if isinstance(value, str):
                parsed[key] = value.strip()
        return parsed

    def _assemble_detailed(self, parsed: Dict[str, str]) -> str:
        parts = []
        if parsed.get('summary'):
            parts.append(f"## SUMMARY\n{parsed['summary']}")
        for heading, key in (
            ('Identification Tips', 'identification_tips'),
            ('Size', 'size_comparison'),
            ('Plumage', 'plumage_comparison'),
            ('Behavior', 'behavior_comparison'),
            ('Habitat', 'habitat_comparison'),
            ('Vocalization', 'vocalization_comparison'),
        ):
            if parsed.get(key):
                parts.append(f'### {heading}\n{parsed[key]}')
        return '\n\n'.join(parts)

    def _parse_comparison_response(self, response: str, species_1_name: str, species_2_name: str) -> Dict[str, str]:
        """Fallback parser for markdown-shaped replies."""
        result = {key: '' for key in _JSON_KEYS}
        result['detailed_comparison'] = response or ''
        sections = {
            'summary': r'## SUMMARY\s*\n(.*?)(?=##|$)',
            'size_comparison': r'### Size\s*\n(.*?)(?=###|##|$)',
            'plumage_comparison': r'### Plumage\s*\n(.*?)(?=###|##|$)',
            'behavior_comparison': r'### Behavior\s*\n(.*?)(?=###|##|$)',
            'habitat_comparison': r'### Habitat\s*\n(.*?)(?=###|##|$)',
            'vocalization_comparison': r'### Vocalization\s*\n(.*?)(?=###|##|$)',
            'identification_tips': r'### Identification Tips\s*\n(.*?)(?=###|##|$)',
        }
        for key, pattern in sections.items():
            match = re.search(pattern, response or '', re.DOTALL | re.IGNORECASE)
            if match:
                result[key] = match.group(1).strip()
        if not result['summary']:
            first_para = (response or '').split('\n\n')[0]
            result['summary'] = first_para[:500]
        return result

    def generate_family_comparison(self, family_1: str, family_2: str, species_list_1: List, species_list_2: List) -> Dict[str, str]:
        prompt = f"""Compare the following two bird families and describe their key differences:

FAMILY 1: {family_1}
Representative species: {', '.join(species_list_1[:10])}

FAMILY 2: {family_2}
Representative species: {', '.join(species_list_2[:10])}

Return JSON with keys summary and detailed_comparison."""
        full_comparison = self._call_openai(prompt, max_tokens=2000, json_object=True)
        if not full_comparison:
            return {'summary': '', 'detailed_comparison': ''}
        try:
            data = json.loads(full_comparison)
        except json.JSONDecodeError:
            return {
                'summary': full_comparison.split('\n\n')[0],
                'detailed_comparison': full_comparison,
            }
        if not isinstance(data, dict):
            return {'summary': full_comparison, 'detailed_comparison': full_comparison}
        return {
            'summary': (data.get('summary') or '').strip(),
            'detailed_comparison': (data.get('detailed_comparison') or data.get('summary') or '').strip(),
        }
