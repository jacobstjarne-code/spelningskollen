"""Scoring-motor för personaliserade spelningsrekommendationer.

score_event(event, user_id) → 0.0–1.0

Komponenter (vikter):
  genre_match   0.35
  artist_match  0.30
  venue         0.15
  popularitet   0.10
  recency       0.10

Score cachelagras i event_scores — beräknas aldrig i realtid i API:t.
"""
from __future__ import annotations

import json
from datetime import date
from .db.database import get_connection
from .matching import normalize_artist


def _get_genre_prefs(user_id: int, conn) -> dict[str, float]:
    rows = conn.execute(
        "SELECT genre, weight FROM user_genre_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["genre"]: r["weight"] for r in rows}


def _get_venue_prefs(user_id: int, conn) -> dict[int, float]:
    rows = conn.execute(
        "SELECT venue_id, weight FROM user_venue_preferences WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {r["venue_id"]: r["weight"] for r in rows}


def _get_followed_artists(user_id: int, conn) -> set[str]:
    rows = conn.execute(
        "SELECT artist_name FROM artist_follows",
    ).fetchall()
    return {normalize_artist(r["artist_name"]) for r in rows}


def _get_related_set(user_id: int, conn) -> set[str]:
    """Hämta related artists för alla artister användaren följer."""
    followed = _get_followed_artists(user_id, conn)
    related = set()
    for a in followed:
        row = conn.execute(
            "SELECT related_artists FROM artist_enrichment WHERE artist_name = ?",
            (a,),
        ).fetchone()
        if row and row["related_artists"]:
            try:
                for ra in json.loads(row["related_artists"]):
                    related.add(normalize_artist(ra))
            except Exception:
                pass
    return related


def score_event(event: dict, user_id: int = 1) -> float:
    """Beräkna personaliseringsscore för ett event. Returnerar 0.0–1.0."""
    conn = get_connection()
    try:
        genre_prefs = _get_genre_prefs(user_id, conn)
        venue_prefs = _get_venue_prefs(user_id, conn)
        followed = _get_followed_artists(user_id, conn)
        related = _get_related_set(user_id, conn)
    finally:
        conn.close()

    # --- Genre (0.35) ---
    genre = (event.get("genre") or "").lower()
    genre_score = genre_prefs.get(genre, 0.3) if genre_prefs else 0.3

    # --- Artist (0.30) ---
    artist_norm = normalize_artist(event.get("artist") or "")
    if artist_norm in followed:
        artist_score = 1.0
    elif artist_norm in related:
        artist_score = 0.8
    else:
        artist_score = 0.2

    # --- Venue (0.15) ---
    venue_id = event.get("venue_id")
    if venue_prefs and venue_id and venue_id in venue_prefs:
        venue_score = venue_prefs[venue_id]
    elif venue_prefs:
        venue_score = 0.3
    else:
        venue_score = 0.5

    # --- Popularitet (0.10) ---
    conn2 = get_connection()
    enrichment = conn2.execute(
        "SELECT popularity FROM artist_enrichment WHERE artist_name = ?",
        (event.get("artist"),),
    ).fetchone()
    conn2.close()
    pop = enrichment["popularity"] if enrichment and enrichment["popularity"] else 50
    pop_score = pop / 100.0

    # --- Recency (0.10) ---
    try:
        event_date = date.fromisoformat(event.get("date", "2099-01-01"))
        days = max(0, (event_date - date.today()).days)
        recency_score = max(0.0, 1.0 - days / 180.0)
    except ValueError:
        recency_score = 0.5

    score = (
        0.35 * genre_score +
        0.30 * artist_score +
        0.15 * venue_score +
        0.10 * pop_score +
        0.10 * recency_score
    )
    return round(min(1.0, max(0.0, score)), 4)


def compute_scores_for_user(user_id: int = 1) -> int:
    """
    Räkna om alla event-scores för en användare.
    Lagrar i event_scores-tabellen.
    Returnerar antal beräknade.
    """
    conn = get_connection()
    events = conn.execute(
        """SELECT e.id, e.artist, e.genre, e.date, e.venue_id
           FROM events e
           WHERE e.date >= date('now')
             AND e.canonical_id IS NULL
             AND e.status = 'active'""",
    ).fetchall()
    conn.close()

    count = 0
    for ev in events:
        ev_dict = dict(ev)
        s = score_event(ev_dict, user_id)
        conn2 = get_connection()
        conn2.execute(
            """INSERT OR REPLACE INTO event_scores (event_id, user_id, score, computed_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (ev_dict["id"], user_id, s),
        )
        conn2.commit()
        conn2.close()
        count += 1

    return count
