"""Tester för genre-normalisering."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector.genre import normalize_genre


def test_rock_variants():
    assert normalize_genre("Rock") == "rock"
    assert normalize_genre("Alternative Rock") == "rock"
    assert normalize_genre("Indie") == "rock"
    assert normalize_genre("Punk Rock") == "rock"


def test_elektroniskt_variants():
    assert normalize_genre("Electronic") == "elektroniskt"
    assert normalize_genre("House Music") == "elektroniskt"
    assert normalize_genre("Techno") == "elektroniskt"
    assert normalize_genre("EDM") == "elektroniskt"


def test_jazz_variants():
    assert normalize_genre("Jazz") == "jazz"
    assert normalize_genre("Soul") == "jazz"
    assert normalize_genre("Blues") == "jazz"
    assert normalize_genre("Funk") == "jazz"


def test_hiphop_variants():
    assert normalize_genre("Hip-Hop") == "hiphop"
    assert normalize_genre("Rap") == "hiphop"
    assert normalize_genre("R&B") == "hiphop"


def test_singer_songwriter():
    assert normalize_genre("Singer/Songwriter") == "singer-songwriter"
    assert normalize_genre("Folk") == "singer-songwriter"
    assert normalize_genre("Acoustic") == "singer-songwriter"


def test_klassiskt():
    assert normalize_genre("Classical") == "klassiskt"
    assert normalize_genre("Opera") == "klassiskt"
    assert normalize_genre("Symphony Orchestra") == "klassiskt"


def test_metal():
    assert normalize_genre("Metal") == "metal"
    assert normalize_genre("Heavy Metal") == "metal"
    assert normalize_genre("Death Metal") == "metal"


def test_pop():
    assert normalize_genre("Pop") == "pop"
    assert normalize_genre("Schlager") == "pop"


def test_världsmusik():
    assert normalize_genre("Reggae") == "världsmusik"
    assert normalize_genre("Latin") == "världsmusik"
    assert normalize_genre("Afrobeat") == "världsmusik"


def test_övrigt():
    assert normalize_genre(None) == "övrigt"
    assert normalize_genre("") == "övrigt"
    assert normalize_genre("Comedy") == "övrigt"
    assert normalize_genre("Spoken Word") == "övrigt"


def test_case_insensitive():
    assert normalize_genre("ROCK") == "rock"
    assert normalize_genre("Jazz") == "jazz"
    assert normalize_genre("electronic") == "elektroniskt"
