"""Tester för text_utils."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.text_utils import clean_text, strip_date_from_title, clean_event_title


# ── clean_text ────────────────────────────────────────────────────────────────

def test_clean_html_entities():
    assert clean_text("Bl&aring;s &amp; Jazz") == "Blås & Jazz"
    assert clean_text("K&ouml;penhamn") == "Köpenhamn"
    assert clean_text("&amp;") == "&"


def test_clean_unicode_normalize():
    # Composed vs decomposed ä (two different bytes)
    decomposed = "a\u0308"  # a + combining diaeresis
    assert clean_text(decomposed) == "ä"


def test_clean_zero_width():
    assert clean_text("Art\u200bist") == "Artist"
    assert clean_text("\ufeffBOM i titeln") == "BOM i titeln"


def test_clean_whitespace():
    assert clean_text("  Konsert   i   Stockholm  ") == "Konsert i Stockholm"
    assert clean_text("Rad1\nRad2") == "Rad1 Rad2"


def test_clean_none():
    assert clean_text(None) is None
    assert clean_text("") is None
    assert clean_text("   ") is None


def test_clean_preserves_swedish():
    assert clean_text("Håkan Hellström") == "Håkan Hellström"
    assert clean_text("Södra Teatern") == "Södra Teatern"


# ── strip_date_from_title ─────────────────────────────────────────────────────

def test_strip_iso_date():
    assert strip_date_from_title("Krunegård 2026-06-15") == "Krunegård"
    assert strip_date_from_title("2026-06-15 Orionteatern") == "Orionteatern"


def test_strip_slash_date():
    assert strip_date_from_title("Krunegård 15/6") == "Krunegård"
    assert strip_date_from_title("Artist 4/6-2026") == "Artist"


def test_strip_swedish_month():
    assert strip_date_from_title("Bob Dylan | 23 mars 2026") == "Bob Dylan"
    assert strip_date_from_title("Lars Winnerbäck 4 jan") == "Lars Winnerbäck"


def test_strip_with_separator():
    assert strip_date_from_title("TERRA — 2026-06-15 Orionteatern") == "TERRA — Orionteatern"


def test_strip_no_date_unchanged():
    assert strip_date_from_title("Håkan Hellström") == "Håkan Hellström"
    assert strip_date_from_title("First Aid Kit") == "First Aid Kit"


def test_clean_event_title_combines():
    assert clean_event_title("Bob Dylan | 23 mars 2026") == "Bob Dylan"
    assert clean_event_title(None) is None
    assert clean_event_title("  ") is None
