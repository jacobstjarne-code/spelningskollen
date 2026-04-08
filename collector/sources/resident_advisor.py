"""Resident Advisor GraphQL-integration.

RA har inget publikt API men exponerar ett GraphQL-endpoint som frontendet använder.
Stockholm area ID: 396. Alla events = elektronisk musik.
"""
from __future__ import annotations

import hashlib
import os
from datetime import date, datetime

import requests

from ..db.database import upsert_event
from ..venue_resolver import resolve_venue
from ..text_utils import clean_text

RA_GRAPHQL = "https://ra.co/graphql"
STOCKHOLM_AREA_ID = 396

_QUERY = """
query GetStockholmEvents($page: Int!, $from: DateTime!, $to: DateTime!) {
  eventListings(
    filters: {
      areas: { any: [%(area_id)s] }
      listingDate: { gte: $from, lte: $to }
    }
    pageSize: 50
    page: $page
    sort: { eventDate: ASCENDING }
  ) {
    data {
      id
      listingDate
      event {
        id
        title
        date
        startTime
        contentUrl
        venue { name }
        artists { name }
        genres { name }
        status
      }
    }
    totalResults
  }
}
""" % {"area_id": STOCKHOLM_AREA_ID}

_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Spelningskollen/1.0",
    "Referer": "https://ra.co/",
}


def _fetch_page(page: int, date_from: str, date_to: str) -> dict:
    payload = {
        "query": _QUERY,
        "variables": {"page": page, "from": date_from, "to": date_to},
    }
    resp = requests.post(RA_GRAPHQL, json=payload, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def collect() -> int:
    today = date.today()
    date_from = today.isoformat() + "T00:00:00.000Z"
    # Hämta 90 dagar framåt
    from datetime import timedelta
    date_to = (today + timedelta(days=90)).isoformat() + "T23:59:59.000Z"

    total = 0
    page = 1

    while True:
        try:
            data = _fetch_page(page, date_from, date_to)
        except Exception as e:
            print(f"  [RA] Fel sida {page}: {e}")
            break

        listings = (
            data.get("data", {})
            .get("eventListings", {})
        )
        items = listings.get("data", [])
        total_results = listings.get("totalResults", 0)

        if not items:
            break

        for item in items:
            try:
                ev = item.get("event") or {}
                if not ev:
                    continue

                # Datum
                date_str = ev.get("date", "")
                time_str = ev.get("startTime", "")
                try:
                    event_date = date.fromisoformat(date_str[:10])
                except (ValueError, TypeError):
                    continue

                if event_date < today:
                    continue

                # Artist — ta första ur lineup eller event-titeln
                artists = ev.get("artists") or []
                if artists:
                    artist = clean_text(artists[0].get("name", "")) or ""
                else:
                    artist = clean_text(ev.get("title", "")) or ""

                if not artist:
                    continue

                # Venue
                venue_data = ev.get("venue") or {}
                venue_name = clean_text(venue_data.get("name", "")) or ""
                venue_slug = None
                if venue_name:
                    venue_id = resolve_venue(venue_name, city="Stockholm")
                    if venue_id:
                        from ..db.database import get_connection
                        conn = get_connection()
                        row = conn.execute(
                            "SELECT slug FROM venues WHERE id = ?", (venue_id,)
                        ).fetchone()
                        conn.close()
                        venue_slug = row["slug"] if row else None

                # Biljettlänk
                content_url = ev.get("contentUrl", "")
                ticket_url = f"https://ra.co{content_url}" if content_url else "https://ra.co/events/se/stockholm"

                # Genre — RA = alltid elektronisk
                genres = ev.get("genres") or []
                raw_genre = genres[0]["name"] if genres else "Electronic"

                ext_id = hashlib.md5(
                    f"ra:{ev.get('id', '')}:{event_date}".encode()
                ).hexdigest()[:12]

                upsert_event(
                    source="resident_advisor",
                    external_id=ext_id,
                    venue_slug=venue_slug,
                    artist=artist,
                    title=clean_text(ev.get("title")) if len(artists) > 1 else None,
                    event_date=event_date,
                    event_time=time_str[:5] if time_str else None,
                    genre=raw_genre,
                    image_url=None,
                    ticket_url=ticket_url,
                    ticket_status="on_sale" if ev.get("status") == "LIVE" else "unknown",
                )
                total += 1

            except Exception as e:
                print(f"  [RA] Kunde inte parsa event: {e}")
                continue

        # Kolla om det finns fler sidor
        if page * 50 >= total_results:
            break
        page += 1

    return total
