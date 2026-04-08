"""Venue-resolution för Spelningskollen.

Matchar fria venue-textsträngar (från scrapers) till venue_id i databasen.
Använder exakt match, slug, alias och fuzzy-matching som fallback.
"""
from __future__ import annotations

import re
from .db.database import get_connection

try:
    from thefuzz import fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False

# Kända venue-alias → venue-slug
VENUE_ALIASES: dict[str, list[str]] = {
    "nalen": ["nalen stora scenen", "nalen klubb", "nalen club", "nalen stora salen"],
    "slaktkyrkan": ["slaktkyrkan globen", "slaktkyrkan johanneshov"],
    "sodra-teatern": ["södra teatern", "södra", "mosebacke", "södra teatern stora scen",
                      "södra teatern kägelbanan", "södra teatern mosebacketerrassen"],
    "debaser-strand": ["debaser strand", "debaser hornstulls strand", "debaser nova"],
    "cirkus": ["cirkus stockholm", "cirkus djurgården"],
    "fasching": ["fasching jazz club", "fasching jazzclub"],
    "katalin": ["katalin och all that jazz", "katalin uppsala", "the kaliber room"],
    "berns": ["berns salonger", "berns hotel", "b–k", "b-k"],
    "munchenbryggeriet": ["münchenbryggeriet", "münchen"],
    "avicii-arena": ["avicii arena", "globen", "hovet"],
    "annexet": ["annexet stockholm", "avicii arena annexet"],
    "parksnackan": ["parksnäckan", "parksnackan"],
    "flustret": ["flustret uppsala"],
    "ukk": ["uppsala konsert & kongress", "konsert & kongress"],
}


def _slug_from_name(name: str) -> str:
    """Enkel slug-generering: lowercase + nordiska/tyska tecken → ascii + bindestreck."""
    s = name.lower().strip()
    s = s.replace("å", "a").replace("ä", "a").replace("ö", "o")
    s = s.replace("ü", "u").replace("ø", "o").replace("æ", "ae")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def seed_venue_aliases() -> int:
    """Lägg in alias i databasen. Idempotent."""
    conn = get_connection()
    inserted = 0
    for slug, aliases in VENUE_ALIASES.items():
        venue_row = conn.execute(
            "SELECT id FROM venues WHERE slug = ?", (slug,)
        ).fetchone()
        if not venue_row:
            continue
        venue_id = venue_row["id"]
        for alias in aliases:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO venue_aliases (venue_id, alias) VALUES (?, ?)",
                    (venue_id, alias.lower())
                )
                inserted += 1
            except Exception:
                pass
    conn.commit()
    conn.close()
    return inserted


def resolve_venue(venue_name: str, city: str | None = None) -> int | None:
    """
    Matcha venue-namn till venue_id.

    Prioritetsordning:
    1. Exakt match på venues.name (case-insensitive)
    2. Exakt match på venues.slug
    3. Match på venue_aliases
    4. Fuzzy match (ratio >= 0.85) på venues.name
    5. None om inget matchar
    """
    if not venue_name:
        return None

    name_lower = venue_name.strip().lower()
    conn = get_connection()

    # 1. Exakt namn
    q = "SELECT id FROM venues WHERE LOWER(name) = ?"
    params = [name_lower]
    if city:
        q += " AND city = ?"
        params.append(city)
    row = conn.execute(q, params).fetchone()
    if row:
        conn.close()
        return row["id"]

    # 2. Slug
    slug = _slug_from_name(name_lower)
    row = conn.execute("SELECT id FROM venues WHERE slug = ?", (slug,)).fetchone()
    if row:
        conn.close()
        return row["id"]

    # 3. Alias
    row = conn.execute(
        "SELECT venue_id FROM venue_aliases WHERE alias = ?", (name_lower,)
    ).fetchone()
    if row:
        conn.close()
        return row["venue_id"]

    # 4. Fuzzy
    if _FUZZY_AVAILABLE:
        venues = conn.execute("SELECT id, name FROM venues").fetchall()
        conn.close()
        best_score, best_id = 0.0, None
        for v in venues:
            score = fuzz.ratio(name_lower, v["name"].lower()) / 100.0
            if score > best_score:
                best_score, best_id = score, v["id"]
        if best_score >= 0.85:
            return best_id
    else:
        conn.close()

    return None
