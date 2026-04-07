"""Scraper för Luger (luger.se/konserter).

Luger bokar på många scener i Stockholm & Uppsala:
Slaktkyrkan, Debaser, Hus 7, Cirkus, Münchenbryggeriet, B-K, m.fl.
Filtrerar på Stockholm + Uppsala.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime, timedelta
from .scraper_base import VenueScraper

# Mappa Luger venue-namn till våra slugs
VENUE_MAP = {
    "slaktkyrkan": "slaktkyrkan",
    "debaser strand": "debaser-strand",
    "debaser nova": "debaser-strand",
    "debaser": "debaser-strand",
    "hus 7": "hus-7",
    "cirkus": "cirkus",
    "münchenbryggeriet": "munchenbryggeriet",
    "munchenbryggeriet": "munchenbryggeriet",
    "berns": "berns",
    "nalen": "nalen",
    "södra teatern": "sodra-teatern",
    "fållan": "fallan",
    "fasching": "fasching",
    "under bron": "under-bron",
    "orionteatern": "orionteatern",
    "kraken": "kraken",
    "bryggarsalen": "bryggarsalen",
    "annexet": "annexet",
    "avicii arena": "avicii-arena",
    "globen": "avicii-arena",
    "b\u2013k": "berns",       # B–K (en-dash)
    "b–k": "berns",
    "b-k": "berns",
    "katalin": "katalin",
    "the kaliber room": "katalin",
    "flustret": "flustret",
    "parksnäckan": "parksnackan",
    "ukk": "ukk",
    "uppsala konsert & kongress": "ukk",
}

MONTHS_SV = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

CITIES_INCLUDE = {"stockholm", "uppsala"}


class LugerScraper(VenueScraper):
    venue_slug = "slaktkyrkan"  # Default, men varierar per event
    venue_url = "https://www.luger.se/konserter"

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(self.venue_url)
        if not soup:
            return []

        events = []
        items = soup.select("div.post-item.concert")

        for item in items:
            parsed = self._parse_item(item)
            if parsed:
                events.append(parsed)

        return events

    def collect(self) -> int:
        """Override — varje event kan ha olika venue_slug."""
        from ..db.database import upsert_event
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:luger"
            upsert_event(**ev)
            count += 1
        return count

    def _parse_item(self, item) -> dict | None:
        try:
            # Artist
            title_el = item.select_one(".post-item__title--text")
            if not title_el:
                return None
            artist = title_el.get_text(strip=True)
            if not artist:
                return None

            # Stad — filtrera på Stockholm/Uppsala
            city_el = item.select_one(".post-item__item-term-city")
            city = city_el.get_text(strip=True).lower() if city_el else ""
            if city not in CITIES_INCLUDE:
                return None

            # Venue
            venue_el = item.select_one(".post-item__item-term-venue")
            venue_name = venue_el.get_text(strip=True) if venue_el else ""
            venue_slug = VENUE_MAP.get(venue_name.lower())

            # Datum
            date_el = item.select_one(".post-item__item-date")
            date_text = date_el.get_text(strip=True) if date_el else ""
            event_date = self._parse_date(date_text)
            if not event_date or event_date < date.today():
                return None

            # Biljettlänk
            ticket_el = item.select_one("a.post-item__item-ticket")
            ticket_url = ticket_el.get("href") if ticket_el else None

            # Luger detail-länk (för externt ID)
            detail_link = item.select_one(".post-item__title a")
            detail_href = detail_link.get("href", "") if detail_link else ""

            ext_id = hashlib.md5(f"luger:{artist}:{event_date}".encode()).hexdigest()[:12]

            return {
                "external_id": ext_id,
                "venue_slug": venue_slug,
                "artist": artist,
                "title": None,
                "event_date": event_date,
                "event_time": None,
                "genre": None,
                "ticket_url": ticket_url,
                "ticket_status": "on_sale" if ticket_url else "unknown",
            }
        except Exception as e:
            print(f"  Luger: kunde inte parsa: {e}")
            return None

    def _parse_date(self, text: str) -> date | None:
        """Parsa Luger-datumformat: 'Idag', 'Imorgon', 'Tor 9 Apr', 'Fre 10 Apr'."""
        text = text.strip().lower()
        today = date.today()

        if text in ("idag", "today"):
            return today
        if text in ("imorgon", "tomorrow"):
            return today + timedelta(days=1)

        # "Tor 9 Apr", "Fre 10 Apr"
        match = re.match(r"\w+\s+(\d{1,2})\s+(\w+)", text)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            month = MONTHS_SV.get(month_str)
            if month:
                year = today.year
                try:
                    d = date(year, month, day)
                    if d < today:
                        d = date(year + 1, month, day)
                    return d
                except ValueError:
                    pass

        return None
