"""Biljettsläpp-bevakning för Spelningskollen.

Kollar statusuppdateringar för events i user_lists och skapar reminders
när biljetter släpps eller status förändras.
"""
from __future__ import annotations

from .db.database import get_connection
from .change_detector import detect_changes, record_changes

_STATUS_PRIORITY = {
    "on_sale": 4,
    "sold_out": 3,
    "presale": 2,
    "announced": 1,
    "unknown": 0,
}


def _create_reminder(conn, event_id: int, reminder_type: str) -> None:
    """Skapa en reminder om den inte redan finns."""
    existing_ul = conn.execute(
        "SELECT id FROM user_lists WHERE event_id = ?", (event_id,)
    ).fetchall()
    for ul in existing_ul:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO reminders
                   (user_list_id, event_id, reminder_type, remind_at)
                   VALUES (?, ?, ?, datetime('now'))""",
                (ul["id"], event_id, reminder_type)
            )
        except Exception:
            pass


def update_ticket_status(event_id: int, new_status: str) -> bool:
    """
    Uppdatera ticket_status för ett event.
    Skapar reminder om status ändrats till on_sale och event finns i user_lists.
    Returnerar True om status ändrades.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT ticket_status FROM events WHERE id = ?", (event_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    old_status = row["ticket_status"]
    old_prio = _STATUS_PRIORITY.get(old_status, 0)
    new_prio = _STATUS_PRIORITY.get(new_status, 0)

    if old_status == new_status:
        conn.close()
        return False

    conn.execute(
        "UPDATE events SET ticket_status = ? WHERE id = ?",
        (new_status, event_id)
    )

    # Skapa reminder om biljetter precis släppts
    if new_status == "on_sale" and old_prio < new_prio:
        in_list = conn.execute(
            "SELECT 1 FROM user_lists WHERE event_id = ? LIMIT 1", (event_id,)
        ).fetchone()
        if in_list:
            _create_reminder(conn, event_id, "ticket_release")
            print(f"  Biljettsläpp-reminder skapad för event {event_id}")

    conn.commit()
    conn.close()
    return True


def check_ticket_updates() -> int:
    """
    Kontrollera biljettstatus för events i user_lists.

    Körs varannan timme av schemaläggaren. Hämtar events med okänd
    eller ej till-salu-status och försöker uppdatera från källan.
    Returnerar antal uppdaterade events.
    """
    conn = get_connection()
    # Events i user_lists med outestående status
    events = conn.execute("""
        SELECT DISTINCT e.id, e.source, e.external_id, e.ticket_status, e.ticket_url
        FROM user_lists ul
        JOIN events e ON ul.event_id = e.id
        WHERE e.date >= date('now')
          AND e.ticket_status IN ('unknown', 'presale', 'announced')
          AND e.canonical_id IS NULL
    """).fetchall()
    conn.close()

    updated = 0
    for e in events:
        new_status = _fetch_current_status(e)
        if new_status and new_status != e["ticket_status"]:
            if update_ticket_status(e["id"], new_status):
                updated += 1

    return updated


def _fetch_current_status(event: dict) -> str | None:
    """
    Hämta aktuell biljettstatus för ett event.

    Strategin varierar beroende på källa:
    - ticketmaster: Ticketmaster API
    - scraper:*: Kontrollera ticket_url (HEAD-request eller scrape)
    """
    source = event.get("source", "")
    ticket_url = event.get("ticket_url", "")

    if not ticket_url:
        return None

    if source == "ticketmaster":
        return _check_ticketmaster(event)

    # Enkel HEAD-kontroll: om URL returnerar 200 är det förmodligen till salu
    try:
        import requests
        resp = requests.head(ticket_url, timeout=5, allow_redirects=True, headers={
            "User-Agent": "Spelningskollen/1.0"
        })
        if resp.status_code == 200:
            return "on_sale"
        elif resp.status_code == 404:
            return "unknown"
    except Exception:
        pass

    return None


def _check_ticketmaster(event: dict) -> str | None:
    """Kontrollera Ticketmaster-status via API."""
    import os, requests
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        return None

    ext_id = event.get("external_id", "")
    if not ext_id:
        return None

    try:
        resp = requests.get(
            f"https://app.ticketmaster.com/discovery/v2/events/{ext_id}",
            params={"apikey": api_key},
            timeout=10
        )
        if not resp.ok:
            return None
        data = resp.json()
        sales = data.get("sales", {}).get("public", {})
        if sales.get("startDateTime") and not sales.get("endDateTime"):
            return "on_sale"
        dates = data.get("dates", {})
        if dates.get("status", {}).get("code") == "onsale":
            return "on_sale"
        if dates.get("status", {}).get("code") in ("offsale", "cancelled"):
            return "sold_out"
    except Exception:
        pass

    return None
