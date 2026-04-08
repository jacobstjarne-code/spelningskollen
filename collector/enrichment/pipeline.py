"""Enrichment-pipeline för Spelningskollen.

Kör Spotify-berikning + Claude-fallback för artister utan enrichment-data.
Uppdaterar event-genres baserat på artist_enrichment.
"""
from __future__ import annotations

from ..db.database import get_connection
from .spotify import enrich_artist as spotify_enrich
from .claude_classify import classify_artist as claude_classify
from ..genre import normalize_genre

MAX_PER_RUN = 50


def _save_enrichment(data: dict) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO artist_enrichment
           (artist_name, spotify_id, genres, popularity, related_artists, image_url, source)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["artist_name"], data["spotify_id"], data["genres"],
            data["popularity"], data["related_artists"], data["image_url"],
            data["source"],
        ),
    )
    conn.commit()
    conn.close()


def enrich_pending_artists(max_artists: int = MAX_PER_RUN) -> int:
    """
    Hitta artister i events som saknar enrichment.
    Kör Spotify → Claude-fallback.
    Returnerar antal berikade.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT e.artist FROM events e
           LEFT JOIN artist_enrichment ae ON ae.artist_name = e.artist
           WHERE ae.id IS NULL
             AND e.date >= date('now')
           LIMIT ?""",
        (max_artists,),
    ).fetchall()
    conn.close()

    enriched = 0
    for row in rows:
        artist = row["artist"]
        data = spotify_enrich(artist)
        if not data:
            data = claude_classify(artist)
        if data:
            _save_enrichment(data)
            enriched += 1
        else:
            # Spara ett tomt entry så vi inte försöker igen
            conn2 = get_connection()
            try:
                conn2.execute(
                    "INSERT OR IGNORE INTO artist_enrichment (artist_name, source) VALUES (?, 'none')",
                    (artist,),
                )
                conn2.commit()
            except Exception:
                pass
            finally:
                conn2.close()

    return enriched


def backfill_event_genres() -> int:
    """
    Uppdatera events som saknar genre men vars artist finns i artist_enrichment.
    Returnerar antal uppdaterade.
    """
    import json as _json

    conn = get_connection()
    rows = conn.execute(
        """SELECT e.id, ae.genres
           FROM events e
           JOIN artist_enrichment ae ON ae.artist_name = e.artist
           WHERE e.genre IS NULL AND ae.genres IS NOT NULL AND ae.source != 'none'
           LIMIT 500""",
    ).fetchall()

    updated = 0
    for row in rows:
        try:
            genres = _json.loads(row["genres"] or "[]")
            if genres:
                normalized = normalize_genre(genres[0])
                conn.execute(
                    "UPDATE events SET genre = ?, subgenre = ? WHERE id = ?",
                    (normalized, genres[0], row["id"]),
                )
                updated += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    return updated
