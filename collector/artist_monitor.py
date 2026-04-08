"""Artist-bevakning för Spelningskollen.

Kollar om nya events dyker upp för artister i artist_follows.
Skapar reminders av typen 'new_event_artist' när en ny spelning hittas.
"""
from __future__ import annotations

from .db.database import get_connection
from .matching import normalize_artist

try:
    from thefuzz import fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False


def _artist_matches(follow_name: str, event_artist: str) -> bool:
    """Fuzzy-match för om ett event-artistnamn matchar ett bevakat namn."""
    a = normalize_artist(follow_name)
    b = normalize_artist(event_artist)
    if a == b:
        return True
    if _FUZZY_AVAILABLE:
        return fuzz.ratio(a, b) / 100.0 >= 0.85
    return False


def check_new_events_for_followed_artists() -> int:
    """
    Körs efter varje insamling.

    Matchar nyinsamlade events (senaste 2h) mot artist_follows.
    Skapar reminder med type 'new_event_artist' för träffar.
    Returnerar antal nya reminders.
    """
    conn = get_connection()

    followed = conn.execute(
        "SELECT id, artist_name, notify_new_events FROM artist_follows WHERE notify_new_events = 1"
    ).fetchall()

    if not followed:
        conn.close()
        return 0

    # Nyligen insamlade events (senaste 2h)
    new_events = conn.execute(
        """SELECT e.id, e.artist, e.date, e.venue_id
           FROM events e
           WHERE e.created_at >= datetime('now', '-2 hours')
             AND e.canonical_id IS NULL
             AND e.date >= date('now')"""
    ).fetchall()

    conn.close()

    if not new_events:
        return 0

    created = 0
    for follow in followed:
        for event in new_events:
            if not _artist_matches(follow["artist_name"], event["artist"]):
                continue

            # Kolla om vi redan skapat en reminder för detta par
            conn = get_connection()
            existing = conn.execute(
                """SELECT 1 FROM reminders
                   WHERE event_id = ? AND reminder_type = 'new_event_artist'""",
                (event["id"],)
            ).fetchone()

            if not existing:
                # Hitta user_list_id om spelningen sparats av användaren
                ul = conn.execute(
                    "SELECT id FROM user_lists WHERE event_id = ?", (event["id"],)
                ).fetchone()
                ul_id = ul["id"] if ul else None

                conn.execute(
                    """INSERT OR IGNORE INTO reminders
                       (user_list_id, event_id, reminder_type, remind_at)
                       VALUES (?, ?, 'new_event_artist', datetime('now'))""",
                    (ul_id, event["id"])
                )
                conn.commit()
                created += 1

            conn.close()

    return created
