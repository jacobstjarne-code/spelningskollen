"""Songkick API — kompletterande datakälla för turnéartister."""
from __future__ import annotations

import os
import requests
from datetime import date
from ..db.database import upsert_event

API_KEY = os.environ.get("SONGKICK_API_KEY", "")
API_BASE = "https://api.songkick.com/api/3.0"

# Songkick metro area IDs
METRO_AREAS = {
    "Stockholm": 31412,
    "Uppsala": 46498,
}

# Songkick venue → vår slug (byggs ut efterhand)
VENUE_MAP = {
    "Nalen": "nalen",
    "Slaktkyrkan": "slaktkyrkan",
    "Södra Teatern": "sodra-teatern",
    "Debaser Strand": "debaser-strand",
    "Berns": "berns",
    "Cirkus": "cirkus",
    "Avicii Arena": "avicii-arena",
    "Globen": "avicii-arena",
    "Tele2 Arena": "tele2-arena",
    "Münchenbryggeriet": "munchenbryggeriet",
    "Fasching": "fasching",
    "Katalin": "katalin",
    "Uppsala Konsert & Kongress": "ukk",
}


def fetch_events(city: str, pages: int = 3) -> int:
    """Hämta musikevent från Songkick för en stad."""
    if not API_KEY:
        print("SONGKICK_API_KEY saknas — hoppar över Songkick")
        return 0

    metro_id = METRO_AREAS.get(city)
    if not metro_id:
        print(f"  Songkick: okänd stad '{city}'")
        return 0

    count = 0
    for page in range(1, pages + 1):
        params = {
            "apikey": API_KEY,
            "page": page,
            "per_page": 50,
        }

        try:
            url = f"{API_BASE}/metro_areas/{metro_id}/calendar.json"
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  Songkick API-fel: {e}")
            break

        results = data.get("resultsPage", {})
        events = results.get("results", {}).get("event", [])
        if not events:
            break

        for event in events:
            try:
                # Bara konserter, inte festivaler utan specifik artist
                event_type = event.get("type", "")
                if event_type not in ("Concert", "Festival"):
                    continue

                sk_id = str(event.get("id", ""))
                display_name = event.get("displayName", "")
                start = event.get("start", {})
                event_date_str = start.get("date")
                event_time = start.get("time")

                if not event_date_str:
                    continue

                event_date = date.fromisoformat(event_date_str)
                if event_date < date.today():
                    continue

                # Artist
                performances = event.get("performance", [])
                artist = performances[0].get("displayName") if performances else display_name

                # Venue
                venue_info = event.get("venue", {})
                venue_name = venue_info.get("displayName", "")
                venue_slug = VENUE_MAP.get(venue_name)

                # Biljettlänk
                ticket_url = event.get("uri")

                upsert_event(
                    source="songkick",
                    external_id=sk_id,
                    venue_slug=venue_slug,
                    artist=artist,
                    title=display_name if display_name != artist else None,
                    event_date=event_date,
                    event_time=event_time,
                    ticket_url=ticket_url,
                    ticket_status="on_sale" if event.get("status") == "ok" else "unknown",
                )
                count += 1

            except (KeyError, ValueError) as e:
                print(f"  Songkick: kunde inte parsa event: {e}")
                continue

        total = results.get("totalEntries", 0)
        if page * 50 >= total:
            break

    return count


def collect():
    """Kör insamling för Stockholm och Uppsala."""
    print("Songkick: hämtar Stockholm...")
    sthlm = fetch_events("Stockholm")
    print(f"  {sthlm} events sparade")

    print("Songkick: hämtar Uppsala...")
    uppsala = fetch_events("Uppsala")
    print(f"  {uppsala} events sparade")

    return sthlm + uppsala
