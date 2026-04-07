"""Ticketmaster Discovery API — hämtar events för Stockholm och Uppsala."""
from __future__ import annotations

import os
import requests
from datetime import datetime, date
from ..db.database import upsert_event

API_BASE = "https://app.ticketmaster.com/discovery/v2"
API_KEY = os.environ.get("TICKETMASTER_API_KEY", "")

# Ticketmaster venue-ID → vår slug-mappning
# Dessa hittas via API:ts venue-sök eller manuellt
VENUE_MAP = {
    # Faktiska Ticketmaster venue-IDn (från event-data)
    "Z598xZq2Za7e1": "strawberry-arena",
    "Z198xZq2ZAv1": "cirkus",
    "Z598xZq2ZkA1k": "berns",
    "Z698xZq2Za7wK": "avicii-arena",        # Hovet / Avicii Arena
    "Z698xZq2ZaeDT": "skansen-solliden",     # Sollidenscenen, Skansen
    "Z698xZq2Zaeno": "slaktkyrkan",          # Fryshuset-området
    "Z698xZq2ZaA6l": "debaser-strand",       # Debaser Nova
    "Z698xZq2ZaANu": "munchenbryggeriet",    # Förbindelsehallen
    "Z698xZq2ZaAI2": "grona-lund",           # Portlands - Frihamnen
}


def _parse_event(event: dict) -> dict | None:
    """Parsa ett Ticketmaster-event till vårt format."""
    try:
        name = event.get("name", "")
        event_id = event.get("id", "")

        # Datum och tid
        dates = event.get("dates", {}).get("start", {})
        event_date = dates.get("localDate")
        event_time = dates.get("localTime")
        if not event_date:
            return None

        # Venue
        venues = event.get("_embedded", {}).get("venues", [])
        venue_tm_id = venues[0].get("id") if venues else None
        venue_name = venues[0].get("name", "") if venues else ""
        venue_slug = VENUE_MAP.get(venue_tm_id)

        # Genre
        classifications = event.get("classifications", [])
        genre = None
        subgenre = None
        if classifications:
            genre = classifications[0].get("genre", {}).get("name")
            subgenre = classifications[0].get("subGenre", {}).get("name")
            # Skippa "Undefined"
            if genre == "Undefined":
                genre = None
            if subgenre == "Undefined":
                subgenre = None

        # Bild
        images = event.get("images", [])
        image_url = None
        for img in images:
            if img.get("ratio") == "16_9" and img.get("width", 0) >= 500:
                image_url = img.get("url")
                break
        if not image_url and images:
            image_url = images[0].get("url")

        # Biljetter
        ticket_url = event.get("url")
        sales = event.get("sales", {}).get("public", {})
        on_sale_date = sales.get("startDateTime")
        ticket_status = "unknown"
        dates_status = event.get("dates", {}).get("status", {}).get("code", "")
        if dates_status == "onsale":
            ticket_status = "on_sale"
        elif dates_status == "offsale":
            ticket_status = "sold_out"

        # Priser
        price_ranges = event.get("priceRanges", [])
        price_min = price_ranges[0].get("min") if price_ranges else None
        price_max = price_ranges[0].get("max") if price_ranges else None

        # Artist — ta från attractions om det finns, annars event name
        attractions = event.get("_embedded", {}).get("attractions", [])
        artist = attractions[0].get("name") if attractions else name

        return {
            "source": "ticketmaster",
            "external_id": event_id,
            "venue_slug": venue_slug,
            "artist": artist,
            "title": name if name != artist else None,
            "event_date": date.fromisoformat(event_date),
            "event_time": event_time,
            "genre": genre,
            "subgenre": subgenre,
            "image_url": image_url,
            "ticket_url": ticket_url,
            "ticket_status": ticket_status,
            "price_min": price_min,
            "price_max": price_max,
            "on_sale_date": on_sale_date,
        }
    except (KeyError, IndexError, ValueError) as e:
        print(f"  Kunde inte parsa event: {e}")
        return None


def fetch_events(city: str = "Stockholm", pages: int = 5) -> int:
    """Hämta musikevent från Ticketmaster för en stad. Returnerar antal sparade."""
    if not API_KEY:
        print("TICKETMASTER_API_KEY saknas — hoppar över Ticketmaster")
        return 0

    count = 0
    for page in range(pages):
        params = {
            "apikey": API_KEY,
            "city": city,
            "countryCode": "SE",
            "classificationName": "Music",
            "size": 50,
            "page": page,
            "sort": "date,asc",
        }

        try:
            resp = requests.get(f"{API_BASE}/events.json", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  Ticketmaster API-fel (sida {page}): {e}")
            break

        events = data.get("_embedded", {}).get("events", [])
        if not events:
            break

        for event in events:
            parsed = _parse_event(event)
            if parsed:
                upsert_event(**parsed)
                count += 1

        # Kolla om det finns fler sidor
        total_pages = data.get("page", {}).get("totalPages", 0)
        if page + 1 >= total_pages:
            break

    return count


def collect():
    """Kör insamling för Stockholm och Uppsala."""
    print("Ticketmaster: hämtar Stockholm...")
    sthlm = fetch_events("Stockholm")
    print(f"  {sthlm} events sparade")

    print("Ticketmaster: hämtar Uppsala...")
    uppsala = fetch_events("Uppsala")
    print(f"  {uppsala} events sparade")

    return sthlm + uppsala
