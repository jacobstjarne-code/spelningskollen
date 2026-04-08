"""Veckans picks — push-notis med Top 5 spelningar nästa vecka.

Körs varje måndag via GitHub Actions / Render Cron.
reminder_type = 'weekly_digest'
"""
from __future__ import annotations

from datetime import date, timedelta
from .db.database import get_connection
from .push import check_and_send_reminders


def schedule_weekly_digest(user_id: int = 1) -> int:
    """
    Hitta top 5 events nästa vecka baserat på event_scores.
    Skapa 'weekly_digest'-reminders som skickas omedelbart.
    Returnerar antal skapade reminders.
    """
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    next_sunday = next_monday + timedelta(days=6)

    conn = get_connection()

    top_events = conn.execute(
        """SELECT e.id, e.artist, e.date, es.score
           FROM events e
           JOIN event_scores es ON es.event_id = e.id AND es.user_id = ?
           WHERE e.date BETWEEN ? AND ?
             AND e.canonical_id IS NULL
             AND e.status = 'active'
           ORDER BY es.score DESC
           LIMIT 5""",
        (user_id, str(next_monday), str(next_sunday)),
    ).fetchall()

    if not top_events:
        conn.close()
        return 0

    created = 0
    for ev in top_events:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO reminders
                   (event_id, reminder_type, remind_at)
                   VALUES (?, 'weekly_digest', datetime('now'))""",
                (ev["id"],),
            )
            created += 1
        except Exception:
            pass

    conn.commit()
    conn.close()

    # Skicka direkt
    if created:
        check_and_send_reminders()

    return created
