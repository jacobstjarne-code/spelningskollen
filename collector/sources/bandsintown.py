"""Bandsintown API-integration.

Hämtar kommande spelningar för bevakade artister + en seed-lista av svenska artister.
API: https://rest.bandsintown.com/artists/{name}/events?app_id=xxx
Gratis, ingen OAuth.
"""
from __future__ import annotations

import os
import hashlib
from datetime import date, datetime

import requests

from ..db.database import get_connection, upsert_event
from ..venue_resolver import resolve_venue
from ..text_utils import clean_text
from ..genre import normalize_genre

APP_ID = os.environ.get("BANDSINTOWN_APP_ID", "spelningskollen")
BASE_URL = "https://rest.bandsintown.com/artists"

CITIES = {"stockholm", "uppsala"}

SEED_ARTISTS = [
    "José González", "Robyn", "The Hives", "Mando Diao",
    "First Aid Kit", "Håkan Hellström", "Veronica Maggio",
    "Lars Winnerbäck", "Melissa Horn", "Daniel Adams-Ray",
    "Tove Lo", "Zara Larsson", "Bladee", "Yung Lean",
    "Little Dragon", "Refused", "Meshuggah", "Opeth",
    "In Flames", "Amon Amarth", "Ghost", "Icona Pop",
    "Mapei", "Seinabo Sey", "Anna Ternheim",
    "Kristian Matsson", "Fever Ray", "Loney Dear", "Amason",
    "Håkan Hellström", "Bob Hund", "Kent",
]


def _fetch_artist_events(artist_name: str) -> list[dict]:
    """Hämta kommande events för en artist. Returnerar tom lista vid fel/404."""
    try:
        resp = requests.get(
            f"{BASE_URL}/{requests.utils.quote(artist_name)}/events",
            params={"app_id": APP_ID},
            timeout=10,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return []
        return data
    except Exception as e:
        print(f"  [Bandsintown] {artist_name}: {e}")
        return []


def _save_event(artist_name: str, event: dict) -> bool:
    """Parsa och spara ett Bandsintown-event. Returnerar True om sparat."""
    venue_data = event.get("venue", {})
    city = (venue_data.get("city") or "").strip()
    country = (venue_data.get("country") or "").strip().upper()

    if city.lower() not in CITIES or country not in ("SE", ""):
        return False

    # Datum
    dt_str = event.get("datetime", "")
    try:
        dt = datetime.fromisoformat(dt_str)
        event_date = dt.date()
        event_time = dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return False

    if event_date < date.today():
        return False

    # Venue
    venue_name = clean_text(venue_data.get("name", ""))
    venue_id_resolved = resolve_venue(venue_name or "", city)
    venue_slug: str | None = None
    if venue_id_resolved:
        conn = get_connection()
        row = conn.execute("SELECT slug FROM venues WHERE id = ?", (venue_id_resolved,)).fetchone()
        conn.close()
        venue_slug = row["slug"] if row else None

    # Biljettlänk
    ticket_url = event.get("url", "")
    offers = event.get("offers", [])
    for offer in offers:
        if offer.get("type", "").lower() == "tickets":
            ticket_url = offer.get("url", ticket_url)
            break

    # Status
    ticket_status = "unknown"
    for offer in offers:
        status = offer.get("status", "").lower()
        if status == "available":
            ticket_status = "on_sale"
            break
        elif status in ("unavailable", "sold out"):
            ticket_status = "sold_out"

    ext_id = hashlib.md5(
        f"bandsintown:{artist_name}:{event_date}:{venue_name}".encode()
    ).hexdigest()[:12]

    upsert_event(
        source="bandsintown",
        external_id=ext_id,
        venue_slug=venue_slug,
        artist=clean_text(artist_name) or artist_name,
        title=None,
        event_date=event_date,
        event_time=event_time if event_time != "00:00" else None,
        genre=None,
        image_url=None,
        ticket_url=ticket_url or None,
        ticket_status=ticket_status,
    )
    return True


def collect() -> int:
    """Hämta events för alla följda artister + seed-lista."""
    conn = get_connection()
    followed = conn.execute("SELECT artist_name FROM artist_follows").fetchall()
    conn.close()

    artists = [r["artist_name"] for r in followed] + SEED_ARTISTS
    artists = list(dict.fromkeys(artists))  # Deduplicera, bevara ordning

    total = 0
    for artist in artists:
        events = _fetch_artist_events(artist)
        for event in events:
            try:
                if _save_event(artist, event):
                    total += 1
            except Exception as e:
                print(f"  [Bandsintown] {artist} event: {e}")

    return total
