"""Scraper för All Things Live (allthingslive.se).

All Things Live bokar artister i hela Sverige.
Hämtar via WP REST API (custom post type 'event' med ACF-fält).
Filtrerar på Stockholm + Uppsala.
"""
from __future__ import annotations

import hashlib
import requests
from datetime import date

from ..db.database import upsert_event
from ..venue_resolver import resolve_venue
from ..text_utils import clean_text

BASE_URL = "https://www.allthingslive.se/wp-json/wp/v2/event"
CITIES_INCLUDE = {"stockholm", "uppsala"}


def _ticket_status(acf_status) -> str:
    if not acf_status or not isinstance(acf_status, dict):
        return "unknown"
    val = acf_status.get("value", "")
    mapping = {
        "on_sale": "on_sale",
        "sold_out": "sold_out",
        "presale": "presale",
        "announced": "announced",
    }
    return mapping.get(val, "unknown")


def _fetch_page(session: requests.Session, page: int) -> list[dict]:
    resp = session.get(
        BASE_URL,
        params={"per_page": 100, "page": page, "_embed": "true"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def collect() -> int:
    """Hämta ATL-events för Stockholm & Uppsala. Returnerar antal sparade."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Spelningskollen/1.0"})

    # Hämta första sidan för att se hur många det finns
    try:
        resp = session.get(BASE_URL, params={"per_page": 100, "page": 1}, timeout=20)
        resp.raise_for_status()
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        first_page = resp.json()
    except Exception as e:
        print(f"  ATL: Kunde inte hämta sida 1: {e}")
        return 0

    all_events: list[dict] = list(first_page)
    for page in range(2, total_pages + 1):
        try:
            all_events.extend(_fetch_page(session, page))
        except Exception as e:
            print(f"  ATL: Sida {page} misslyckades: {e}")
            break

    today = date.today()
    saved = 0

    for ev in all_events:
        try:
            acf = ev.get("acf") or {}

            # Datum
            date_str = acf.get("date_start")
            if not date_str:
                continue
            try:
                event_date = date.fromisoformat(date_str[:10])
            except ValueError:
                continue
            if event_date < today:
                continue

            # Venue & stad
            venue_data = acf.get("venue")
            if not venue_data or not isinstance(venue_data, dict):
                continue
            venue_acf = venue_data.get("acf") or {}
            city = (venue_acf.get("city") or "").strip()
            if city.lower() not in CITIES_INCLUDE:
                continue

            venue_name = venue_data.get("name") or ""
            venue_id = resolve_venue(venue_name, city) if venue_name else None

            # Venue slug — fallback via venues-tabellen
            venue_slug = None
            if venue_id:
                from ..db.database import get_connection
                row = get_connection().execute(
                    "SELECT slug FROM venues WHERE id = ?", (venue_id,)
                ).fetchone()
                if row:
                    venue_slug = row["slug"]

            # Artist / titel
            raw_title = (ev.get("title") or {}).get("rendered") or ""
            artist = clean_text(raw_title)
            if not artist:
                continue

            # Ticket
            ticket_url = acf.get("ticket_url") or None
            status = _ticket_status(acf.get("status"))

            ext_id = hashlib.md5(
                f"atl:{artist}:{date_str}:{venue_name}".encode()
            ).hexdigest()[:16]

            upsert_event(
                source="scraper:allthingslive",
                external_id=ext_id,
                venue_slug=venue_slug,
                artist=artist,
                title=None,
                event_date=event_date,
                ticket_url=ticket_url,
                ticket_status=status,
            )
            saved += 1

        except Exception as e:
            print(f"  ATL: Kunde inte parsa event: {e}")

    return saved
