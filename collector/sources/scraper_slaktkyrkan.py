"""Scraper för Slaktkyrkan / Slakthusområdet (slfrk.com / slfrk.com/slaktkyrkan)."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper


class SlaktkyrkanScraper(VenueScraper):
    venue_slug = "slaktkyrkan"
    venue_url = "https://www.slfrk.com"

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(self.venue_url)
        if not soup:
            return []

        events = []
        # SLFRK (Slakthusområdets Förening) listar events på startsidan
        for item in soup.select(".event, .eventlist-event, article, .summary-item"):
            try:
                title_el = item.select_one("h2, h3, .summary-title, .event-title, .eventlist-title")
                if not title_el:
                    continue
                artist = title_el.get_text(strip=True)
                if not artist:
                    continue

                date_el = item.select_one("time, .summary-metadata-item--date, .event-date")
                date_str = ""
                if date_el:
                    date_str = date_el.get("datetime", "") or date_el.get_text(strip=True)

                event_date = self._parse_date(date_str)
                if not event_date or event_date < date.today():
                    continue

                link_el = item.select_one("a[href]")
                ticket_url = None
                if link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/"):
                        ticket_url = f"{self.venue_url}{href}"
                    elif href.startswith("http"):
                        ticket_url = href

                ext_id = hashlib.md5(f"slaktkyrkan:{artist}:{event_date}".encode()).hexdigest()[:12]

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
                print(f"  Slaktkyrkan: kunde inte parsa event: {e}")
                continue

        return events

    def _parse_date(self, date_str: str) -> date | None:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M"]:
            try:
                return datetime.strptime(date_str[:19], fmt[:len(fmt)]).date()
            except ValueError:
                continue
        return None
