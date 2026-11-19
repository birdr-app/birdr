"""AI vision labels for the plumage of a bird photo (sex, stage, season).

`classify_images` is the only function that talks to the API; the `label_media_plumage` command
calls it through one name so tests can stub it. By default it uses the Message Batches API (half
price, results within an hour or so); `direct=True` makes one request per photo instead.

Needs the `anthropic` package and credentials (ANTHROPIC_API_KEY, or `ant auth login`).
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable, Dict, Iterable, List, Optional

DEFAULT_MODEL = 'claude-haiku-5-5'  # cheapest current model with vision
PROMPT_VERSION = 'v1'
BATCH_SIZE = 1000

LABEL_SCHEMA = {
    'type': 'object',
    'properties': {
        'sex': {'type': 'string', 'enum': ['male', 'female', 'unknown']},
        'stage': {'type': 'string', 'enum': ['adult', 'immature', 'juvenile', 'chick', 'unknown']},
        'season': {'type': 'string', 'enum': ['breeding', 'non_breeding', 'eclipse', 'unknown']},
        'confidence': {'type': 'number'},
    },
    'required': ['sex', 'stage', 'season', 'confidence'],
    'additionalProperties': False,
}

SYSTEM = (
    'You are an expert field ornithologist labelling bird photos for a birding course. '
    'Judge only what the photo itself shows: the plumage and bare parts of the bird, not the '
    'caption, background or what is typical for the species. If a field cannot be told from this '
    'photo (a monomorphic species, a distant or hidden bird, no bird at all), answer "unknown" '
    'for it. A wrong label is worse than "unknown".'
)


def model_version(model: str = DEFAULT_MODEL) -> str:
    return f'{model}:{PROMPT_VERSION}'


def build_prompt(species: str, latin: str) -> str:
    return (
        f'The photo shows a {species} ({latin}). Label the main bird:\n'
        '- sex: "male" or "female" when the plumage shows it, else "unknown".\n'
        '- stage: "adult", "immature" (older than juvenile, not yet adult), "juvenile" (first '
        'plumage after leaving the nest), "chick" (downy), else "unknown".\n'
        '- season: the plumage aspect: "breeding" (nuptial/summer plumage), "non_breeding" (winter '
        'plumage), "eclipse" (duck eclipse plumage), else "unknown". For species that look the '
        'same all year use "unknown".\n'
        '- confidence: 0 to 1, how sure you are of the labels you gave other than "unknown" '
        '(the lowest of them). Use 0.9 or more only when the field marks are clearly visible.'
    )


_SIZED = re.compile(r'/(original|large)\.(jpe?g|png)$')


def image_url_for_ai(url: str) -> str:
    """A mid-size version when the host has one (iNaturalist 'medium', 500 px): cheaper and plenty to see plumage."""
    return _SIZED.sub(r'/medium.\2', url or '')


def build_request(item: Dict, model: str = DEFAULT_MODEL) -> Dict:
    """Message parameters for one photo; `item` has `url`, `species` and `latin`."""
    return {
        'model': model,
        'max_tokens': 1024,  # thinking counts toward this
        'system': SYSTEM,
        'output_config': {'effort': 'low', 'format': {'type': 'json_schema', 'schema': LABEL_SCHEMA}},
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'url', 'url': image_url_for_ai(item['url'])}},
                {'type': 'text', 'text': build_prompt(item['species'], item['latin'])},
            ],
        }],
    }


def parse_label(text: str) -> Optional[Dict]:
    """The label {sex, stage, season, confidence} from the model's JSON; '' for unknown. None if unusable."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out = {}
    for field, allowed in (('sex', LABEL_SCHEMA['properties']['sex']['enum']),
                           ('stage', LABEL_SCHEMA['properties']['stage']['enum']),
                           ('season', LABEL_SCHEMA['properties']['season']['enum'])):
        value = str(data.get(field) or 'unknown').strip().lower()
        out[field] = value if value in allowed and value != 'unknown' else ''
    try:
        out['confidence'] = max(0.0, min(1.0, float(data.get('confidence'))))
    except (TypeError, ValueError):
        return None
    return out


def label_from_message(message) -> Optional[Dict]:
    """The label of a Messages API response; None on a refusal, truncation or a missing/invalid JSON text."""
    if getattr(message, 'stop_reason', None) in ('refusal', 'max_tokens'):
        return None
    text = next((b.text for b in message.content if getattr(b, 'type', '') == 'text'), None)
    return parse_label(text)


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError('The AI labeller needs the anthropic package: pip install anthropic') from exc
    return anthropic.Anthropic()


def _custom_id(media_id: int) -> str:
    return f'm{media_id}'


def collect_batch(batch_id: str, client=None) -> Dict[int, Optional[Dict]]:
    """{media id: label or None} of a finished batch. Errored, expired and cancelled requests give None."""
    client = client or _client()
    out: Dict[int, Optional[Dict]] = {}
    for entry in client.messages.batches.results(batch_id):
        media_id = int(entry.custom_id.lstrip('m'))
        out[media_id] = label_from_message(entry.result.message) if entry.result.type == 'succeeded' else None
    return out


def wait_for_batch(batch_id: str, client=None, poll_seconds: float = 30, log: Callable[[str], None] = lambda s: None):
    client = client or _client()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == 'ended':
            return batch
        log(f'  batch {batch_id}: {batch.request_counts.processing} still processing')
        time.sleep(poll_seconds)


def classify_images(
    items: Iterable[Dict],
    model: str = DEFAULT_MODEL,
    direct: bool = False,
    poll_seconds: float = 30,
    batch_size: int = BATCH_SIZE,
    log: Callable[[str], None] = lambda s: None,
    client=None,
) -> Dict[int, Optional[Dict]]:
    """Label photos. `items`: dicts with `media_id`, `url`, `species`, `latin`.

    Returns {media_id: {sex, stage, season, confidence} or None}; None means no usable answer (the
    photo could not be fetched, the model refused, ...) and the photo can be tried again later.
    """
    items = list(items)
    client = client or _client()
    out: Dict[int, Optional[Dict]] = {}
    if direct:
        import anthropic

        for item in items:
            try:
                out[item['media_id']] = label_from_message(client.messages.create(**build_request(item, model)))
            except anthropic.APIStatusError:
                out[item['media_id']] = None
        return out

    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batch_ids: List[str] = []
    for i in range(0, len(items), batch_size):
        chunk = items[i:i + batch_size]
        batch = client.messages.batches.create(requests=[
            Request(custom_id=_custom_id(item['media_id']),
                    params=MessageCreateParamsNonStreaming(**build_request(item, model)))
            for item in chunk
        ])
        batch_ids.append(batch.id)
        log(f'  submitted batch {batch.id} ({len(chunk)} photos); '
            f'collect later with --resume-batch {batch.id} if this run is interrupted')
    for batch_id in batch_ids:
        wait_for_batch(batch_id, client, poll_seconds, log)
        out.update(collect_batch(batch_id, client))
    return out
