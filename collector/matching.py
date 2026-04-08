"""Korsreferens-matchningsmotor för Spelningskollen.

Hittar och mergar events som samlats in från flera källor men är samma spelning.
"""
from __future__ import annotations

import re
from .db.database import get_connection

try:
    from thefuzz import fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# Normalisering
# ──────────────────────────────────────────────────────────────────────────────

_PARENS = re.compile(r"\([^)]*\)")
_STRIP_WORDS = re.compile(
    r"(?<!\w)(feat\.?|ft\.?|featuring|presents?)(?!\w)|(?<!\w)(and|och|med|with)(?!\w)|\s*&\s*",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")


def normalize_artist(name: str) -> str:
    """Normalisera artistnamn för jämförelse."""
    s = name.lower()
    s = _PARENS.sub("", s)          # Ta bort (SE), (feat. X) etc.
    s = _STRIP_WORDS.sub(" ", s)    # Ta bort feat., &, med etc.
    s = _WHITESPACE.sub(" ", s)
    return s.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Matchning
# ──────────────────────────────────────────────────────────────────────────────

def find_matches(event_id: int) -> list[dict]:
    """
    Givet ett event-ID, hitta möjliga dubbletter från andra källor.

    Söker:
    a) Samma venue_id + datum ±1 dag
    b) Samma stad + samma datum + ingen venue_id på endera

    Returnerar lista med:
      { canonical_id, candidate_id, confidence, match_method }
    """
    conn = get_connection()
    event = conn.execute(
        """SELECT e.id, e.artist, e.date, e.venue_id, e.source,
                  v.city
           FROM events e
           LEFT JOIN venues v ON e.venue_id = v.id
           WHERE e.id = ?""",
        (event_id,)
    ).fetchone()
    conn.close()

    if not event:
        return []

    candidates: list = []

    # Strategi a: samma venue + datum ±1 dag
    if event["venue_id"]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT e.id, e.artist, e.date, e.source FROM events e
               WHERE e.venue_id = ?
                 AND e.date BETWEEN date(?, '-1 day') AND date(?, '+1 day')
                 AND e.id != ?
                 AND e.canonical_id IS NULL""",
            (event["venue_id"], event["date"], event["date"], event_id)
        ).fetchall()
        conn.close()
        candidates.extend([(r, False) for r in rows])  # False = exakt datum

    # Strategi b: samma stad, exakt datum, en av dem saknar venue
    if event["city"]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT e.id, e.artist, e.date, e.source FROM events e
               LEFT JOIN venues v ON e.venue_id = v.id
               WHERE (e.venue_id IS NULL OR ? IS NULL)
                 AND v.city = ?
                 AND e.date = ?
                 AND e.id != ?
                 AND e.canonical_id IS NULL""",
            (event["venue_id"], event["city"], event["date"], event_id)
        ).fetchall()
        conn.close()
        candidates.extend([(r, False) for r in rows])

    if not candidates:
        return []

    norm_a = normalize_artist(event["artist"])
    seen_pairs: set = set()
    matches = []

    for cand, date_differs in candidates:
        if cand["source"] == event["source"]:
            continue

        pair_key = tuple(sorted([event_id, cand["id"]]))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        norm_b = normalize_artist(cand["artist"])

        if norm_a == norm_b:
            confidence = 1.0
            method = "exact"
        elif _FUZZY_AVAILABLE:
            ratio = fuzz.ratio(norm_a, norm_b) / 100.0
            if ratio < 0.85:
                continue
            confidence = ratio
            method = "fuzzy_artist"
        else:
            continue

        # Reducera confidence om datum skiljer 1 dag
        if cand["date"] != event["date"]:
            confidence = max(0.0, confidence - 0.05)
            method = method + "_date_offset"

        canonical_id = min(event_id, cand["id"])
        candidate_id = max(event_id, cand["id"])

        matches.append({
            "canonical_id": canonical_id,
            "candidate_id": candidate_id,
            "confidence": round(confidence, 3),
            "match_method": method,
        })

    return matches


# ──────────────────────────────────────────────────────────────────────────────
# Merge
# ──────────────────────────────────────────────────────────────────────────────

_STATUS_PRIORITY = {
    "on_sale": 4,
    "sold_out": 3,
    "presale": 2,
    "announced": 1,
    "unknown": 0,
}


def merge_events(canonical_id: int, duplicate_id: int) -> bool:
    """
    Merga duplicate in i canonical.

    Berikar canonical med data från duplicate om canonical saknar det.
    Returnerar True om merge gjordes.
    """
    conn = get_connection()

    canonical = conn.execute("SELECT * FROM events WHERE id = ?", (canonical_id,)).fetchone()
    duplicate = conn.execute("SELECT * FROM events WHERE id = ?", (duplicate_id,)).fetchone()

    if not canonical or not duplicate:
        conn.close()
        return False

    updates: dict = {}

    # Berika med saknade fält från duplicate
    for field in ["image_url", "ticket_url", "price_min", "price_max", "on_sale_date",
                  "genre", "subgenre", "description", "time", "doors_open"]:
        if not canonical.get(field) and duplicate.get(field):
            updates[field] = duplicate[field]

    # Biljettstatus — välj högst prioritet
    canon_prio = _STATUS_PRIORITY.get(canonical.get("ticket_status", "unknown"), 0)
    dup_prio = _STATUS_PRIORITY.get(duplicate.get("ticket_status", "unknown"), 0)
    if dup_prio > canon_prio:
        updates["ticket_status"] = duplicate["ticket_status"]

    # Uppdatera canonical om vi har berikningar
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [canonical_id]
        conn.execute(f"UPDATE events SET {set_clause} WHERE id = ?", params)

    # Markera duplicate som merged
    conn.execute(
        "UPDATE events SET canonical_id = ? WHERE id = ?",
        (canonical_id, duplicate_id)
    )

    # Flytta user_lists-rader
    conn.execute(
        "UPDATE user_lists SET event_id = ? WHERE event_id = ?",
        (canonical_id, duplicate_id)
    )

    # Spara matchningsrelation
    try:
        conn.execute(
            """INSERT OR IGNORE INTO event_matches
               (canonical_event_id, matched_event_id, confidence, match_method, verified)
               VALUES (?, ?, 1.0, 'merged', 1)""",
            (canonical_id, duplicate_id)
        )
    except Exception:
        pass

    conn.commit()
    conn.close()
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Spara kandidat (för manuell verifiering)
# ──────────────────────────────────────────────────────────────────────────────

def save_match_candidate(
    canonical_id: int,
    candidate_id: int,
    confidence: float,
    method: str,
) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO event_matches
               (canonical_event_id, matched_event_id, confidence, match_method)
               VALUES (?, ?, ?, ?)""",
            (canonical_id, candidate_id, confidence, method)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Post-collect: kör matchning på nyinsamlade events
# ──────────────────────────────────────────────────────────────────────────────

def post_collect_match(new_event_ids: list[int]) -> tuple[int, int]:
    """
    Kör matchning efter insamling.
    Returnerar (antal auto-mergade, antal kandidater sparade).
    """
    merged = 0
    candidates = 0

    for eid in new_event_ids:
        matches = find_matches(eid)
        for m in matches:
            if m["confidence"] >= 0.95:
                if merge_events(m["canonical_id"], m["candidate_id"]):
                    merged += 1
            elif m["confidence"] >= 0.85:
                save_match_candidate(
                    m["canonical_id"], m["candidate_id"],
                    m["confidence"], m["match_method"]
                )
                candidates += 1

    return merged, candidates
