"""Scraper för Nalen (nalen.com)."""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper


class NalenScraper(VenueScraper):
    venue_slug = "nalen"
    venue_url = "https://www.nalen.com/kalendarium"

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(self.venue_url)
        if not soup:
            return []

        events = []
        # Nalen använder typiskt event-cards med datum och artistnamn
        # Strukturen kan ändras — detta är en startpunkt
        for item in soup.select(".event-item, .eventlist-event, article.event, .list-item"):
            try:
                # Försök hitta titel/artist
                title_el = item.select_one("h2, h3, .title, .event-title, .eventlist-title")
                if not title_el:
                    continue
                artist = title_el.get_text(strip=True)

                # Datum
                date_el = item.select_one("time, .date, .event-date, .eventlist-meta-date")
                date_str = ""
                if date_el:
                    date_str = date_el.get("datetime", "") or date_el.get_text(strip=True)

                event_date = self._parse_date(date_str)
                if not event_date or event_date < date.today():
                    continue

                # Länk
                link_el = item.select_one("a[href]")
                ticket_url = None
                if link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/"):
                        ticket_url = f"https://www.nalen.com{href}"
                    elif href.startswith("http"):
                        ticket_url = href

                # Generera ett stabilt externt ID
                ext_id = hashlib.md5(f"nalen:{artist}:{event_date}".encode()).hexdigest()[:12]

                events.append({
                    "external_id": ext_id,
                    "artist": artist,
                    "title": None,
                    "event_date": event_date,
                    "event_time": None,
                    "genre": None,
                    "ticket_url": ticket_url or self.venue_url,
                    "ticket_status": "on_sale",
                })
            except Exception as e:
                print(f"  Nalen: kunde inte parsa event: {e}")
                continue

        return events

    def _parse_date(self, date_str: str) -> date | None:
        """Parsa datum i olika format."""
        if not date_str:
            return None

        # ISO-format (datetime-attribut)
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]:
            try:
                return datetime.strptime(date_str[:len("2026-01-01T00:00:00")], fmt).date()
            except ValueError:
                continue

        # Svenska datumformat: "15 apr 2026", "15 april", etc.
        months_sv = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
            "januari": 1, "februari": 2, "mars": 3, "april": 4, "juni": 6,
            "juli": 7, "augusti": 8, "september": 9, "oktober": 10,
            "november": 11, "december": 12,
        }
        match = re.search(r"(\d{1,2})\s+(\w+)\s*(\d{4})?", date_str.lower())
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            year = int(match.group(3)) if match.group(3) else date.today().year
            month = months_sv.get(month_str)
            if month:
                try:
                    return date(year, month, day)
                except ValueError:
                    pass

        return None
