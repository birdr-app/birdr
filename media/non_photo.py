"""Recognise Wikimedia files that are not photos of a bird, from the file name.

Commons file names describe their content well: range maps end in ``_dist`` or
mention a map, book plates name their illustrator (Keulemans, Naumann, Gould) or
the plate number, and plant books that share a genus with birds (``Oenanthe
aquatica``) name the herbal they come from.

``classify`` returns ``('clear', reason)`` for files that are certainly not a bird
photo, ``('unclear', reason)`` for ones a person should look at, or None. Used by
the ``sweep_nonphoto_media`` command and by the Wikimedia scraper at import.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

CLEAR = 'clear'
UNCLEAR = 'unclear'

# Possessives are species names on real photos: Gould's Petrel, Audubon's Oriole.
_NOT_POSSESSIVE = r"(?!['’]s\b)"

_RULES: list[tuple[str, str, str]] = [
    # 'dist' / 'range' only as the last word: Species_name_dist.png (not 'Kandy dist' locations).
    (CLEAR, 'range map', r'(?:\bdist$|(?<!mountain )(?<!hill )(?<!close )\brange$|\b(?:distribution|range ?maps?|maps?|verbreitung(?:skarte)?|karte|area de distribucion)\b)'),
    (CLEAR, 'book plate', r'\b(?:plates?|pl \d+|lithograph|chromolithograph|keulemans|naumann)\b'),
    (CLEAR, 'book plate', rf'\b(?:gould|audubon|wolf|richter|smit|hart)\b{_NOT_POSSESSIVE}(?=.*\b(?:by|gould|richter|plate|birds of|keulemans|lithograph)\b)'),
    (CLEAR, 'book plate', rf'\bby (?:john |george edward |louis agassiz )?(?:gould|audubon|keulemans|naumann|lodge|thorburn|frohawk|fuertes|wolf|lear){_NOT_POSSESSIVE}\b'),
    (CLEAR, 'artwork', r'\b(?:drawing|drawings|painting|paintings|illustration|illustrations|illustrated|watercolou?r(?:ed)?|engraving|artwork|sketch|print|prints|iconographia|lccn\d+)\b'),
    (CLEAR, 'plant', r'\b(?:pflanzen|medizinal|kohler|köhler|herbarium)\b'),
    (CLEAR, 'specimen', r'\b(?:study skins?|specimens?|stuffed|taxidermy|taxidermied|skeleton|skulls?|bones?|mounted)\b'),
    (CLEAR, 'egg', r'\b(?:eggs?|clutch)\b'),
    # A bird at its nest is still a bird photo.
    (UNCLEAR, 'nest', r'\bnests?\b'),
    (CLEAR, 'stamp or coin', r'\b(?:stamps?|postage|briefmarke|coins?|medals?|emblem|logo|coat of arms)\b'),
    (CLEAR, 'diagram', r'\b(?:diagram|chart|cladogram|phylogeny|spectrogram|sonogram)\b'),
    (UNCLEAR, 'scientific figure', r'\b(?:figure|fig \d+|bdj|zookeys)\b'),
    (UNCLEAR, 'museum', r'\b(?:museum|museo|naturalis|collection)\b'),
    (UNCLEAR, 'skin', r'\bskins?\b'),
]
_COMPILED = [(kind, reason, re.compile(pattern)) for kind, reason, pattern in _RULES]
_UNCLEAR_EXTENSIONS = {'png': 'png file', 'svg': 'svg file', 'tif': 'scan', 'tiff': 'scan', 'djvu': 'scan', 'pdf': 'scan'}


def file_name_text(url_or_title: str) -> tuple[str, str]:
    """Lower-case words of a Commons file name, and its extension."""
    value = url_or_title or ''
    if '://' in value:
        value = urlparse(value).path.rsplit('/', 1)[-1]
    value = unquote(value)
    value = re.sub(r'^(?:file|image|bestand|datei):', '', value, flags=re.I)
    value = re.sub(r'^\d+px-', '', value)
    base, dot, ext = value.rpartition('.')
    if not dot:
        base, ext = value, ''
    text = re.sub(r"[_\-–—.,;()\[\]{}+&=]+", ' ', base).lower()
    return ' '.join(text.split()), ext.lower()


def classify(url_or_title: str) -> tuple[str, str] | None:
    text, ext = file_name_text(url_or_title)
    for kind, reason, pattern in _COMPILED:
        if kind == CLEAR and pattern.search(text):
            return kind, reason
    for kind, reason, pattern in _COMPILED:
        if kind == UNCLEAR and pattern.search(text):
            return kind, reason
    if ext in _UNCLEAR_EXTENSIONS:
        return UNCLEAR, _UNCLEAR_EXTENSIONS[ext]
    return None
