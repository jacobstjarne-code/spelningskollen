"""Scraper för Kaliber Live (kaliberlive.com).

Kaliber är en arrangör/venue-grupp i Uppsala med indie/alternativ-profil.
Bokar på The Kaliber Room Uppsala, Katalin/All that Jazz, Blackbird, Gasklockorna m.fl.

Hämtar eventlistan från /events/ — all data finns i listningsidan.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date, timedelta
from .scraper_base import VenueScraper
from ..venue_resolver import resolve_venue
from ..db.database import upsert_event, get_connection

BASE_URL = "https://kaliberlive.com/events/"

MONTHS_SV = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

VENUE_MAP = {
    "the kaliber room uppsala": "katalin",
    "the kaliber room":         "katalin",
    "kaliber room":             "katalin",
    "katalin and all that jazz": "katalin",
    "blackbird":                "blackbird",
    "gasklockorna":             "gasklockorna",
}


def _parse_date(text: str) -> date | None:
    """Parsa 'Onsdag 8 april' eller 'Onsdag 8 april 2026' → date."""
    text = text.strip().lower()
    # Strip weekday prefix
    text = re.sub(r"^[a-zåäö]+\s+", "", text)
    # With year: "8 april 2026"
    m = re.match(r"(\d{1,2})\s+([a-zåäö]+)\s+(\d{4})", text)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
        month = MONTHS_SV.get(month_str)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass
    # Without year: "8 april" — pick nearest future occurrence
    m = re.match(r"(\d{1,2})\s+([a-zåäö]+)", text)
    if m:
        day, month_str = int(m.group(1)), m.group(2)
        month = MONTHS_SV.get(month_str)
        if month:
            today = date.today()
            for year in (today.year, today.year + 1):
                try:
                    d = date(year, month, day)
                    if d >= today - timedelta(days=1):
                        return d
                except ValueError:
                    pass
    return None


class KaliberScraper(VenueScraper):
    venue_slug = "katalin"   # Default; åsidosätts per event
    venue_url = BASE_URL

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(BASE_URL)
        if not soup:
            return []

        events = []
        for item in soup.select(".events__list-item"):
            parsed = self._parse_item(item)
            if parsed:
                events.append(parsed)
        return events

    def collect(self) -> int:
        """Override — venue_slug varierar per event."""
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:kaliber"
            upsert_event(**ev)
            count += 1
        return count

    def _parse_item(self, item) -> dict | None:
        try:
            parts = item.get_text(separator="|", strip=True).split("|")
            parts = [p for p in parts if p and p not in ("Läs mer", "Boka biljett")]

            if not parts:
                return None

            # "UTSÅLT" / "FÅTAL KVAR" kan vara första elementet
            sold_out = False
            idx = 0
            if parts[0].upper() in ("UTSÅLT", "SLUTSÅLT"):
                sold_out = True
                idx = 1
            elif "FÅTAL" in parts[0].upper():
                idx = 1

            if len(parts) < idx + 2:
                return None

            date_str = parts[idx]
            artist = self.clean(parts[idx + 1])
            venue_text = parts[idx + 2].lower() if len(parts) > idx + 2 else ""

            if not artist or not date_str:
                return None

            event_date = _parse_date(date_str)
            if not event_date or event_date < date.today():
                return None

            venue_slug = VENUE_MAP.get(venue_text)
            if not venue_slug and venue_text:
                venue_slug = VENUE_MAP.get(venue_text.strip())

            # Ticket link — "Boka biljett"-länk (extern, ej kaliberlive.com)
            ticket_url = None
            for a in item.select("a[href]"):
                href = a.get("href", "")
                if "kaliberlive.com" not in href and any(
                    t in href for t in ["ticket", "biljett", "nortic", "tickster", "ticketmaster", "billetto"]
                ):
                    ticket_url = href
                    break

            # Biljettlänk utan externt keyword — fallback till eventdetaljsida
            if not ticket_url:
                detail_a = item.select_one("a[href*='kaliberlive.com/events/']")
                if detail_a:
                    ticket_url = detail_a.get("href")

            ticket_status = "sold_out" if sold_out else ("on_sale" if ticket_url else "unknown")

            # Genre från class-namn (allt utom layout-klasser)
            genre_classes = [
                c for c in item.get("class", [])
                if c not in ("events__list-item", "events__list-item--usual", "events__list-item--sponsored")
                and not c.startswith("events__")
                and "+" not in c          # venue-klasser innehåller "+"
                and c.lower() not in VENUE_MAP
            ]
            genre_raw = genre_classes[0].replace("+", " ").lower() if genre_classes else None

            ext_id = hashlib.md5(
                f"kaliber:{artist}:{event_date}:{venue_slug or venue_text}".encode()
            ).hexdigest()[:16]

            return {
                "external_id": ext_id,
                "venue_slug": venue_slug,
                "artist": artist,
                "title": None,
                "event_date": event_date,
                "genre": genre_raw,
                "ticket_url": ticket_url,
                "ticket_status": ticket_status,
            }
        except Exception as e:
            print(f"  Kaliber: parse-fel: {e}")
            return None
