"""Detekterar förändringar i event-data (datum, venue, status, inställt)."""
from __future__ import annotations

from .db.database import get_connection

TRACKED_FIELDS = ["date", "time", "venue_id", "ticket_status", "price_min", "price_max"]


def detect_changes(existing: dict, incoming: dict) -> list[dict]:
    """
    Jämför befintligt event med inkommande data.
    Returnerar lista med {field, old_value, new_value} för fält som ändrats.
    """
    changes = []
    for field in TRACKED_FIELDS:
        old = str(existing.get(field) or "")
        new = str(incoming.get(field) or "")
        if new and old != new:
            changes.append({"field": field, "old_value": old, "new_value": new})
    return changes


def record_changes(event_id: int, changes: list[dict]) -> None:
    """Spara detekterade förändringar i event_changes-tabellen."""
    if not changes:
        return
    conn = get_connection()
    for change in changes:
        conn.execute(
            """INSERT INTO event_changes (event_id, field, old_value, new_value)
               VALUES (?, ?, ?, ?)""",
            (event_id, change["field"], change["old_value"], change["new_value"])
        )
    conn.commit()
    conn.close()


def mark_cancelled(event_id: int) -> None:
    """Markera ett event som inställt och skapa reminder om det finns i user_lists."""
    conn = get_connection()
    conn.execute(
        "UPDATE events SET status = 'cancelled' WHERE id = ?",
        (event_id,)
    )
    # Skapa reminder för alla som sparat eventet
    lists = conn.execute(
        "SELECT id, event_id FROM user_lists WHERE event_id = ?",
        (event_id,)
    ).fetchall()
    for ul in lists:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO reminders
                   (user_list_id, event_id, reminder_type, remind_at)
                   VALUES (?, ?, 'event_cancelled', datetime('now'))""",
                (ul["id"], event_id)
            )
        except Exception:
            pass
    conn.commit()
    conn.close()


def check_cancellations(venue_id: int, active_external_ids: list[str]) -> int:
    """
    Kolla om events i DB för given venue saknas i ny insamling.

    active_external_ids: externa ID:n som fortfarande är aktiva (från senaste scraping).
    Returnerar antal events markerade som inställda.
    """
    if not active_external_ids:
        return 0

    conn = get_connection()
    # Events i DB för denna venue som snart inträffar
    rows = conn.execute(
        """SELECT id, external_id, artist, date FROM events
           WHERE venue_id = ? AND date BETWEEN date('now') AND date('now', '+60 days')
           AND status = 'active' AND canonical_id IS NULL""",
        (venue_id,)
    ).fetchall()
    conn.close()

    cancelled = 0
    active_set = set(active_external_ids)
    for row in rows:
        if row["external_id"] and row["external_id"] not in active_set:
            print(f"  Inställt: {row['artist']} ({row['date']}) — syns inte längre")
            mark_cancelled(row["id"])
            cancelled += 1

    return cancelled
