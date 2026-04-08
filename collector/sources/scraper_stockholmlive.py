"""Scraper för Stockholm Live (stockholmlive.com).

Täcker: Avicii Arena, Annexet, Strawberry Arena, Hovet, Södra Teatern.
Parsas via JSON-LD (strukturerade eventdata) + HTML (venue, bild, biljettlänk).
"""
from __future__ import annotations

import json
import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper
from ..db.database import upsert_event

BASE_URL = "https://www.stockholmlive.com"
LISTING_URL = f"{BASE_URL}/evenemang"

# Stockholm Live venue-namn → vår slug (hoppa över utländska venues)
VENUE_MAP = {
    "avicii arena": "avicii-arena",
    "annexet": "annexet",
    "strawberry arena": "strawberry-arena",
    "hovet": "avicii-arena",   # Samma komplex
    "södra teatern": "sodra-teatern",
    "södra teatern – stora scen": "sodra-teatern",
    "södra teatern – kägelbanan": "sodra-teatern",
    "södra teatern – mosebacketerrassen": "sodra-teatern",
}

MONTHS_SV = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "aug": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


class StockholmLiveScraper(VenueScraper):
    venue_slug = "avicii-arena"  # Default, varierar per event
    venue_url = LISTING_URL

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(LISTING_URL)
        if not soup:
            return []

        # --- Steg 1: Hämta JSON-LD för namn + datum ---
        ld_events: dict[str, dict] = {}  # name → {date, detail_url}
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        ev = item.get("item", {})
                        name = ev.get("name", "").strip()
                        start = ev.get("startDate", "")
                        url = ev.get("url", "")
                        if name and start:
                            ld_events[name] = {"start": start, "url": url}
            except (json.JSONDecodeError, AttributeError):
                continue

        # --- Steg 2: Hämta HTML-cards för venue + bild + biljettlänk ---
        events = []
        today = date.today()

        # Event-cards är <a> med <h3> inuti
        cards = soup.select("#events-listing-container a")
        if not cards:
            # Fallback: alla <a> med <h3>
            cards = [a for a in soup.select("a") if a.select_one("h3")]

        seen = set()

        for card in cards:
            try:
                h3 = card.select_one("h3")
                if not h3:
                    continue

                artist = h3.get_text(strip=True)
                if not artist or artist in seen:
                    continue
                seen.add(artist)

                # Venue från span
                spans = card.select("span")
                venue_slug = None
                event_date = None

                for span in spans:
                    text = span.get_text(strip=True).lower()
                    # Venue-match
                    if not venue_slug:
                        for venue_key, slug in VENUE_MAP.items():
                            if venue_key in text:
                                venue_slug = slug
                                break
                    # Datum-match: "8 april 2026" eller "8 april – 9 april 2026"
                    if not event_date:
                        event_date = self._parse_date_text(span.get_text(strip=True))

                if not venue_slug:
                    continue  # Hoppa venues vi inte spårar

                # Datum från JSON-LD om vi inte hittade det i HTML
                if not event_date and artist in ld_events:
                    start_str = ld_events[artist]["start"]
                    try:
                        event_date = datetime.fromisoformat(start_str).date()
                    except ValueError:
                        pass

                if not event_date or event_date < today:
                    continue

                # Bild
                img = card.select_one("img")
                image_url = (
                    img.get("data-lazy-src") or img.get("src")
                ) if img else None

                # Biljettlänk — letaefter "Köp biljett"-länk i närheten
                ticket_url = None
                # Kolla syskon-element i parent
                parent = card.parent
                if parent:
                    for a in parent.select('a[href*="ticketmaster"], a[href*="axs.com"], a[href*="tickster"], a[href*="livenation"]'):
                        ticket_url = a.get("href")
                        break
                if not ticket_url:
                    ticket_url = ld_events.get(artist, {}).get("url") or card.get("href") or LISTING_URL

                ext_id = hashlib.md5(
                    f"stockholmlive:{artist}:{event_date}".encode()
                ).hexdigest()[:12]

                events.append({
                    "external_id": ext_id,
                    "venue_slug": venue_slug,
                    "artist": artist,
                    "title": None,
                    "event_date": event_date,
                    "event_time": None,
                    "genre": None,
                    "image_url": image_url,
                    "ticket_url": ticket_url,
                    "ticket_status": "on_sale",
                })

            except Exception as e:
                print(f"  StockholmLive: kunde inte parsa: {e}")
                continue

        # --- Fallback: Bygg events enbart från JSON-LD om HTML misslyckades ---
        if not events and ld_events:
            events = self._events_from_jsonld(ld_events, today)

        return events

    def _events_from_jsonld(self, ld_events: dict, today: date) -> list[dict]:
        """Bygg minimala events från enbart JSON-LD-data."""
        results = []
        for artist, data in ld_events.items():
            try:
                dt = datetime.fromisoformat(data["start"])
                event_date = dt.date()
                if event_date < today:
                    continue
                ext_id = hashlib.md5(f"stockholmlive:{artist}:{event_date}".encode()).hexdigest()[:12]
                results.append({
                    "external_id": ext_id,
                    "venue_slug": "avicii-arena",  # Bäst gissning utan venue-info
                    "artist": artist,
                    "title": None,
                    "event_date": event_date,
                    "event_time": None,
                    "genre": None,
                    "image_url": None,
                    "ticket_url": data.get("url") or LISTING_URL,
                    "ticket_status": "on_sale",
                })
            except Exception:
                continue
        return results

    def _parse_date_text(self, text: str) -> date | None:
        """Parsa 'April 8, 2026', '8 april 2026', '8 apr – 9 apr 2026' etc."""
        text = text.strip().lower()
        # "8 april 2026" eller "8 apr 2026"
        m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
        if m:
            day = int(m.group(1))
            month = MONTHS_SV.get(m.group(2))
            year = int(m.group(3))
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass
        return None

    def collect(self) -> int:
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:stockholmlive"
            upsert_event(**ev)
            count += 1
        return count
