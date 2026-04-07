"""Scraper för Södra Teatern (sodrateatern.com)."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper


class SodraTeaternScraper(VenueScraper):
    venue_slug = "sodra-teatern"
    venue_url = "https://www.sodrateatern.com/evenemang"

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(self.venue_url)
        if not soup:
            return []

        events = []
        for item in soup.select(".event-card, .event-item, article.event, .list-item, .summary-item"):
            try:
                title_el = item.select_one("h2, h3, .event-title, .summary-title")
                if not title_el:
                    continue
                artist = title_el.get_text(strip=True)

                date_el = item.select_one("time, .event-date, .date")
                date_str = date_el.get("datetime", "") if date_el else ""
                if not date_str and date_el:
                    date_str = date_el.get_text(strip=True)

                event_date = self._parse_date(date_str)
                if not event_date or event_date < date.today():
                    continue

                link_el = item.select_one("a[href]")
                ticket_url = None
                if link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/"):
                        ticket_url = f"https://www.sodrateatern.com{href}"
                    elif href.startswith("http"):
                        ticket_url = href

                ext_id = hashlib.md5(f"sodrateatern:{artist}:{event_date}".encode()).hexdigest()[:12]

                events.append({
                    "external_id": ext_id,
                    "artist": artist,
                    "title": None,
                    "event_date": event_date,
                    "event_time": None,
                    "genre": None,
                    "ticket_url": ticket_url,
                    "ticket_status": "on_sale",
                })
            except Exception as e:
                print(f"  Södra Teatern: kunde inte parsa: {e}")
                continue

        return events

    def _parse_date(self, date_str: str) -> date | None:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]:
            try:
                return datetime.strptime(date_str[:19], fmt).date()
            except ValueError:
                continue
        return None
