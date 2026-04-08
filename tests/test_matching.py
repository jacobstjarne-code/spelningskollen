"""Tester för matchningsmotor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.matching import normalize_artist, find_matches, merge_events


def test_normalize_removes_feat():
    assert normalize_artist("John Doe feat. Jane") == "john doe jane"
    assert normalize_artist("The Band ft. Someone") == "the band someone"


def test_normalize_removes_parens():
    assert normalize_artist("John Doe (SE)") == "john doe"
    assert normalize_artist("Artist (Live Band)") == "artist"


def test_normalize_removes_connectors():
    assert normalize_artist("John & Jane") == "john jane"
    assert normalize_artist("Band with Orchestra") == "band orchestra"


def test_normalize_lowercases():
    assert normalize_artist("The Rolling Stones") == "the rolling stones"
    assert normalize_artist("ABBA") == "abba"


def test_normalize_strips_whitespace():
    result = normalize_artist("  John   Doe  ")
    assert result == "john doe"


def test_normalize_same_result_for_variants():
    """Varianter av samma artist ska normalisera till samma sträng."""
    a = normalize_artist("John Doe Trio (SE)")
    b = normalize_artist("John Doe Trio")
    assert a == b


def test_normalize_feat_variants():
    a = normalize_artist("Artist feat. Guest")
    b = normalize_artist("Artist ft. Guest")
    c = normalize_artist("Artist featuring Guest")
    # Alla ska ta bort konnektorn
    assert "feat" not in a
    assert "ft" not in b
    assert "featuring" not in c
