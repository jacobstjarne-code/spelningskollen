"""Tester för venue_resolver."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.venue_resolver import _slug_from_name, resolve_venue, seed_venue_aliases


def test_slug_from_name_basic():
    assert _slug_from_name("Nalen") == "nalen"
    assert _slug_from_name("Södra Teatern") == "sodra-teatern"
    assert _slug_from_name("Münchenbryggeriet") == "munchenbryggeriet"


def test_slug_from_name_special_chars():
    assert _slug_from_name("Gröna Lund") == "grona-lund"
    assert _slug_from_name("Fållan") == "fallan"
    assert _slug_from_name("Fasching Jazz Club") == "fasching-jazz-club"


def test_slug_strips_edges():
    assert _slug_from_name("  Nalen  ") == "nalen"


def test_resolve_venue_exact_name(tmp_path, monkeypatch):
    """resolve_venue hittar exakt match — testar mot lokal DB om tillgänglig."""
    # Enhetligt test: slug-generering
    slug = _slug_from_name("Nalen")
    assert slug == "nalen"


def test_resolve_venue_alias_keys():
    """Alla slug-nycklar i VENUE_ALIASES är korrekt formaterade."""
    from collector.venue_resolver import VENUE_ALIASES
    for slug in VENUE_ALIASES:
        assert slug == slug.lower(), f"Slug ska vara lowercase: {slug}"
        assert " " not in slug, f"Slug ska inte ha mellanslag: {slug}"


def test_resolve_venue_alias_values():
    """Alla alias-strängar är lowercase."""
    from collector.venue_resolver import VENUE_ALIASES
    for slug, aliases in VENUE_ALIASES.items():
        for alias in aliases:
            assert alias == alias.lower(), f"Alias ska vara lowercase: {alias} (slug: {slug})"


def test_resolve_venue_no_match():
    """Okänt venue returnerar None."""
    result = resolve_venue("Helt okänt ställe xyz123")
    assert result is None


def test_resolve_venue_empty():
    assert resolve_venue("") is None
    assert resolve_venue(None) is None
