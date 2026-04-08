"""Implicit profilbyggning för Spelningskollen.

record_interaction() — spara signal + uppdatera genre/venue-vikter.
Signalvikter:
  save    +0.15
  buy     +0.25
  click   +0.03
  unsave  -0.05
  dismiss -0.10

Alla vikter clampas 0.0–1.0.
"""
from __future__ import annotations

from .db.database import get_connection

SIGNAL_WEIGHTS = {
    "save":    +0.15,
    "buy":     +0.25,
    "click":   +0.03,
    "unsave":  -0.05,
    "dismiss": -0.10,
}


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _update_genre_weight(user_id: int, genre: str, delta: float, conn) -> None:
    if not genre:
        return
    row = conn.execute(
        "SELECT weight FROM user_genre_preferences WHERE user_id = ? AND genre = ?",
        (user_id, genre),
    ).fetchone()
    current = row["weight"] if row else 0.5
    new_weight = _clamp(current + delta)
    conn.execute(
        """INSERT OR REPLACE INTO user_genre_preferences (user_id, genre, weight)
           VALUES (?, ?, ?)""",
        (user_id, genre, new_weight),
    )


def _update_venue_weight(user_id: int, venue_id: int | None, delta: float, conn) -> None:
    if not venue_id:
        return
    row = conn.execute(
        "SELECT weight FROM user_venue_preferences WHERE user_id = ? AND venue_id = ?",
        (user_id, venue_id),
    ).fetchone()
    current = row["weight"] if row else 0.5
    new_weight = _clamp(current + delta)
    conn.execute(
        """INSERT OR REPLACE INTO user_venue_preferences (user_id, venue_id, weight)
           VALUES (?, ?, ?)""",
        (user_id, venue_id, new_weight),
    )


def record_interaction(user_id: int, event_id: int, interaction_type: str) -> None:
    """
    Spara interaktion och uppdatera genre/venue-vikter.
    interaction_type: 'click', 'save', 'buy', 'unsave', 'dismiss'
    """
    delta = SIGNAL_WEIGHTS.get(interaction_type, 0.0)

    conn = get_connection()

    # Logga interaktionen
    conn.execute(
        """INSERT INTO user_interactions (user_id, event_id, interaction_type)
           VALUES (?, ?, ?)""",
        (user_id, event_id, interaction_type),
    )

    if delta != 0.0:
        # Hämta event-info för att uppdatera vikter
        ev = conn.execute(
            "SELECT genre, venue_id FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if ev:
            _update_genre_weight(user_id, ev["genre"], delta, conn)
            _update_venue_weight(user_id, ev["venue_id"], delta, conn)

    conn.commit()
    conn.close()


def get_profile(user_id: int = 1) -> dict:
    """Returnera profil-snapshot för en användare."""
    conn = get_connection()

    profile = conn.execute(
        "SELECT onboarding_done FROM user_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    genres = conn.execute(
        "SELECT genre, weight FROM user_genre_preferences WHERE user_id = ? ORDER BY weight DESC",
        (user_id,),
    ).fetchall()

    venues = conn.execute(
        """SELECT v.name, v.slug, v.city, upv.weight
           FROM user_venue_preferences upv
           JOIN venues v ON v.id = upv.venue_id
           WHERE upv.user_id = ?
           ORDER BY upv.weight DESC""",
        (user_id,),
    ).fetchall()

    artists = conn.execute(
        "SELECT artist_name FROM artist_follows ORDER BY added_at DESC",
    ).fetchall()

    conn.close()

    return {
        "onboarding_done": bool(profile["onboarding_done"]) if profile else False,
        "genres": [{"genre": r["genre"], "weight": r["weight"]} for r in genres],
        "venues": [dict(r) for r in venues],
        "followed_artists": [r["artist_name"] for r in artists],
    }


def save_onboarding(user_id: int, genres: list[str], venue_slugs: list[str], artists: list[str]) -> None:
    """Spara onboarding-val. Sätt initala vikter 0.8 för valda genres/venues."""
    conn = get_connection()

    # Sätt genre-prefs
    for genre in genres:
        conn.execute(
            """INSERT OR REPLACE INTO user_genre_preferences (user_id, genre, weight)
               VALUES (?, ?, 0.8)""",
            (user_id, genre),
        )

    # Sätt venue-prefs
    for slug in venue_slugs:
        row = conn.execute("SELECT id FROM venues WHERE slug = ?", (slug,)).fetchone()
        if row:
            conn.execute(
                """INSERT OR REPLACE INTO user_venue_preferences (user_id, venue_id, weight)
                   VALUES (?, ?, 0.8)""",
                (user_id, row["id"]),
            )

    # Lägg till artistbevakning
    for artist in artists:
        if artist.strip():
            conn.execute(
                "INSERT OR IGNORE INTO artist_follows (artist_name) VALUES (?)",
                (artist.strip(),),
            )

    # Markera onboarding klar
    conn.execute(
        """INSERT OR REPLACE INTO user_profile (user_id, onboarding_done, updated_at)
           VALUES (?, 1, CURRENT_TIMESTAMP)""",
        (user_id,),
    )

    conn.commit()
    conn.close()
