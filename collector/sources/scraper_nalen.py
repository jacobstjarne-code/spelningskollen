"""Scraper för Nalen (nalen.com).

Nalen kör Storyblok/Nuxt.js. Event-listan finns server-side renderad på
/sv/konserter-event som kort med class="Link" (Tailwind, ingen semantisk klass).

Dataextraktion per event-länk:
- Artist:  div.top-info > p  (eller img[alt] → regex)
- Datum:   img[alt] "Artist DD månad YYYY Nalen Stockholm"
- Biljett: länkhref absolut → https://nalen.com/sv/konsert/{slug}
"""
from __future__ import annotations

import re
import hashlib
from datetime import date, timedelta
from .scraper_base import VenueScraper
from ..db.database import upsert_event

EVENTS_URL = "https://nalen.com/sv/konserter-event"
BASE_URL    = "https://nalen.com"

MONTHS_SV = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10,
    "november": 11, "december": 12,
}


def _parse_date_from_alt(alt: str) -> tuple[str | None, date | None]:
    """
    Parsa 'Kofi Stone 9 april 2026 Nalen Stockholm'.
    Returnerar (artist, date) eller (None, None).
    """
    alt = alt.strip()
    # Format: "{Artist} DD MMMM YYYY Nalen..."
    m = re.search(r"^(.+?)\s+(\d{1,2})\s+([a-zåäö]+)\s+(\d{4})\s+Nalen", alt, re.IGNORECASE)
    if m:
        artist = m.group(1).strip()
        day    = int(m.group(2))
        month  = MONTHS_SV.get(m.group(3).lower())
        year   = int(m.group(4))
        if month:
            try:
                return artist, date(year, month, day)
            except ValueError:
                pass
    return None, None


def _parse_short_date(text: str) -> date | None:
    """Parsa '09 apr.' eller '13 apr' — år gissas till närmaste framtid."""
    m = re.match(r"(\d{1,2})\s+([a-zåäö]+)", text.strip().lower().rstrip("."))
    if not m:
        return None
    day   = int(m.group(1))
    month = MONTHS_SV.get(m.group(2))
    if not month:
        return None
    today = date.today()
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
            if d >= today - timedelta(days=1):
                return d
        except ValueError:
            pass
    return None


class NalenScraper(VenueScraper):
    venue_slug = "nalen"
    venue_url  = EVENTS_URL

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(EVENTS_URL)
        if not soup:
            return []

        events: list[dict] = []
        seen: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href.startswith("/sv/konsert/"):
                continue

            ev = self._parse_link(link, href)
            if not ev:
                continue

            key = f"{ev['artist']}:{ev['event_date']}"
            if key in seen:
                continue
            seen.add(key)
            events.append(ev)

        return events

    def _parse_link(self, link, href: str) -> dict | None:
        try:
            # --- Artist + datum från img alt (primär källa) ---
            img = link.find("img")
            artist: str | None = None
            event_date: date | None = None

            if img:
                alt = img.get("alt", "")
                artist, event_date = _parse_date_from_alt(alt)

            # Fallback artist: div med class top-info
            if not artist:
                top = link.find("div", class_=lambda c: c and "top-info" in " ".join(c) if isinstance(c, list) else "top-info" in str(c))
                if top:
                    p = top.find("p")
                    if p:
                        artist = self.clean(p.get_text(strip=True))

            # Fallback datum: div justify-self-end
            if not event_date:
                date_div = link.find("div", class_=lambda c: c and "justify-self-end" in " ".join(c) if isinstance(c, list) else "justify-self-end" in str(c))
                if date_div:
                    p = date_div.find("p")
                    if p:
                        event_date = _parse_short_date(p.get_text(strip=True))

            if not artist or not event_date:
                return None
            if event_date < date.today():
                return None

            ticket_url = BASE_URL + href
            image_url  = img.get("src") or img.get("data-src") if img else None

            ext_id = hashlib.md5(
                f"nalen:{artist}:{event_date}".encode()
            ).hexdigest()[:12]

            return {
                "external_id":  ext_id,
                "artist":       artist,
                "title":        None,
                "event_date":   event_date,
                "event_time":   None,
                "genre":        None,
                "image_url":    image_url,
                "ticket_url":   ticket_url,
                "ticket_status": "on_sale",
            }
        except Exception as e:
            print(f"  Nalen: parse-fel: {e}")
            return None

    def collect(self) -> int:
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"]     = "scraper:nalen"
            ev["venue_slug"] = self.venue_slug
            upsert_event(**ev)
            count += 1
        return count
