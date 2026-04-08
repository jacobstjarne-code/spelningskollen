"""Texthantering för Spelningskollen.

Rensar och normaliserar text från scrapers:
- HTML-entities
- Unicode-normalisering
- Osynliga tecken
- Datum ur titlar
"""
from __future__ import annotations

import html
import re
import unicodedata

# ──────────────────────────────────────────────────────────────────────────────
# Grundläggande textrensning
# ──────────────────────────────────────────────────────────────────────────────

def clean_text(text: str | None) -> str | None:
    """Rensa och normalisera text från scrapers."""
    if not text:
        return None

    # 1. Dekoda HTML-entities (&aring; → å, &amp; → &, etc.)
    text = html.unescape(text)

    # 2. Normalisera unicode (NFC — composed form)
    text = unicodedata.normalize("NFC", text)

    # 3. Ta bort noll-bredd-tecken och andra osynliga
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # 4. Normalisera whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text or None


# ──────────────────────────────────────────────────────────────────────────────
# Datum ur titlar
# ──────────────────────────────────────────────────────────────────────────────

_MONTHS = r"(?:jan(?:uari)?|feb(?:ruari)?|mars|apr(?:il)?|maj|jun(?:i)?|jul(?:i)?|aug(?:usti)?|sep(?:tember)?|okt(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_WEEKDAYS = r"(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)"

DATE_PATTERNS = [
    # ISO-format: 2026-06-15
    r"\b\d{4}-\d{2}-\d{2}\b",
    # Kort datum: 15/6, 15/06, 15/6-2026
    r"\b\d{1,2}/\d{1,2}(?:-\d{2,4})?\b",
    # Svenskt med månad: 15 juni, 23 mars 2026, 4 jan
    rf"\b\d{{1,2}}\s+{_MONTHS}\s*(?:\d{{2,4}})?\b",
    # Veckodag + datum: Lördag 15 juni
    rf"\b{_WEEKDAYS}\s+\d{{1,2}}\s+{_MONTHS}\b",
]

_SEPARATOR_CLEANUP = [
    r"\s*[—–\-|]\s*$",   # Trailing separator
    r"^\s*[—–\-|]\s*",   # Leading separator
]

_DATE_RE = [re.compile(p, re.IGNORECASE) for p in DATE_PATTERNS]
_SEP_RE = [re.compile(p) for p in _SEPARATOR_CLEANUP]


def strip_date_from_title(title: str) -> str:
    """Ta bort datum-mönster ur eventtitel."""
    result = title
    for pattern in _DATE_RE:
        result = pattern.sub("", result)
    for pattern in _SEP_RE:
        result = pattern.sub("", result)
    # Kollaps multipla mellanslag som uppstår när datum plockas bort
    result = re.sub(r"  +", " ", result)
    return result.strip()


def clean_event_title(title: str | None) -> str | None:
    """Rensa titel och ta bort datum-mönster."""
    cleaned = clean_text(title)
    if cleaned:
        cleaned = strip_date_from_title(cleaned)
    return cleaned or None
