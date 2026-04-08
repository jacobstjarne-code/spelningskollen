"""Web Push-notiser för Spelningskollen.

Skickar push-notiser för events i user_lists:
- Påminnelse X dagar innan spelning
- Biljettsläpp (ticket_release)
- Inställt event (event_cancelled)
"""
from __future__ import annotations

import os
import json
from .db.database import get_connection

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.environ.get("VAPID_SUBJECT", os.environ.get("VAPID_EMAIL", "mailto:admin@spelningskollen.se"))

try:
    from pywebpush import webpush, WebPushException
    _PUSH_AVAILABLE = True
except ImportError:
    _PUSH_AVAILABLE = False


def _remove_subscription(endpoint: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()


def send_push(subscription: dict, title: str, body: str, url: str = "/") -> bool:
    """
    Skicka push-notis till en prenumerant.
    Returnerar True om lyckades.
    """
    if not _PUSH_AVAILABLE or not VAPID_PRIVATE_KEY:
        return False

    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {
                    "p256dh": subscription["p256dh"],
                    "auth": subscription["auth"],
                }
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_EMAIL}
        )
        return True
    except WebPushException as e:
        if e.response and e.response.status_code == 410:
            # Prenumerationen har gått ut
            _remove_subscription(subscription["endpoint"])
        return False
    except Exception:
        return False


def _format_reminder(reminder: dict) -> dict:
    """Formatera påminnelsetext baserat på typ."""
    artist = reminder.get("artist") or "Okänd artist"
    venue = reminder.get("venue_name") or ""
    date = reminder.get("date") or ""
    rtype = reminder.get("reminder_type", "")

    if rtype == "ticket_release":
        return {
            "title": f"Biljetter ute — {artist}",
            "body": f"{date} · {venue}" if venue else date,
            "url": "/paningar",
        }
    elif rtype == "event_cancelled":
        return {
            "title": f"Inställt: {artist}",
            "body": f"Spelningen {date} på {venue} är inställd." if venue else f"Spelningen {date} är inställd.",
            "url": "/lista",
        }
    else:  # before_event
        return {
            "title": f"Imorgon: {artist}",
            "body": f"{venue}" if venue else date,
            "url": "/lista",
        }


def check_and_send_reminders() -> int:
    """
    Skicka push-notiser för väntande reminders.
    Körs var 15:e minut (kallas från schemaläggare).
    Returnerar antal skickade notiser.
    """
    if not _PUSH_AVAILABLE or not VAPID_PRIVATE_KEY:
        return 0

    conn = get_connection()
    pending = conn.execute("""
        SELECT r.id, r.reminder_type, e.artist, e.title, e.date, e.time,
               v.name as venue_name
        FROM reminders r
        JOIN events e ON r.event_id = e.id
        LEFT JOIN venues v ON e.venue_id = v.id
        WHERE r.sent = 0 AND r.remind_at <= datetime('now')
    """).fetchall()

    subs = conn.execute(
        "SELECT endpoint, p256dh, auth FROM push_subscriptions"
    ).fetchall()
    conn.close()

    if not pending or not subs:
        return 0

    sent_total = 0
    for reminder in pending:
        msg = _format_reminder(dict(reminder))
        sent = 0
        for sub in subs:
            if send_push(dict(sub), msg["title"], msg["body"], msg["url"]):
                sent += 1

        if sent > 0:
            conn2 = get_connection()
            conn2.execute(
                "UPDATE reminders SET sent = 1 WHERE id = ?", (reminder["id"],)
            )
            conn2.commit()
            conn2.close()
            sent_total += sent

    return sent_total


def subscribe(endpoint: str, p256dh: str, auth: str) -> bool:
    """Lägg till push-prenumeration."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO push_subscriptions (endpoint, p256dh, auth)
               VALUES (?, ?, ?)""",
            (endpoint, p256dh, auth)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def unsubscribe(endpoint: str) -> bool:
    """Ta bort push-prenumeration."""
    _remove_subscription(endpoint)
    return True
