"""Scraper för Debaser (debaser.se/kalender)."""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class DebaserScraper(VenueScraper):
    venue_slug = "debaser-strand"
    venue_url = "https://www.debaser.se/kalender"

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(self.venue_url)
        if not soup:
            return []

        events = []
        rows = soup.select(".event-row")

        for row in rows:
            parsed = self._parse_row(row)
            if parsed:
                events.append(parsed)

        return events

    def _parse_row(self, row) -> dict | None:
        try:
            # Artist — .event-name-hero eller .h3.calendar-mobile
            name_el = row.select_one(".event-name-hero")
            if not name_el:
                return None
            artist = name_el.get_text(strip=True)
            if not artist:
                return None

            # Rensa bort "SUPPORT: ..." som klistras fast
            artist = re.split(r"SUPPORT:|SPECIAL GUEST:", artist, flags=re.IGNORECASE)[0].strip()

            # Skippa quiz och liknande
            genre_el = row.select_one(".event-date-hero.black .b2.white")
            genre_text = genre_el.get_text(strip=True).lower() if genre_el else ""
            if genre_text in ("quiz", "club", "klubb"):
                return None

            # Datum — .b1-data elementen: dag, månad, år, veckodag
            b1_els = row.select(".event-date-hero.border .b1-data")
            if len(b1_els) < 3:
                return None

            day_str = b1_els[0].get_text(strip=True)
            month_str = b1_els[1].get_text(strip=True).lower()
            year_str = b1_els[2].get_text(strip=True)

            day = int(day_str)
            month = MONTHS.get(month_str)
            year = int(year_str) if year_str.isdigit() else date.today().year

            if not month:
                return None

            event_date = date(year, month, day)
            if event_date < date.today():
                return None

            # Venue — .b2.aa (andra instansen i row-1-on-event)
            venue_el = row.select_one(".event-date-hero.border-copy .b2.aa")
            venue_name = venue_el.get_text(strip=True) if venue_el else "Debaser"

            # Venue-slug
            venue_slug = "debaser-strand"
            if "nova" in venue_name.lower():
                venue_slug = "debaser-strand"  # Samma venue i vår DB
            elif "strand" in venue_name.lower():
                venue_slug = "debaser-strand"

            # Evenemangslänk + biljett
            event_link = row.select_one("a.event-info")
            event_href = event_link.get("href", "") if event_link else ""
            detail_url = f"https://www.debaser.se{event_href}" if event_href.startswith("/") else event_href

            ticket_el = row.select_one("a.ticket-new[href]:not([href='#'])")
            ticket_url = ticket_el.get("href") if ticket_el else detail_url

            # Slutsålt?
            sale_el = row.select_one(".sale-status")
            sale_text = sale_el.get_text(strip=True).lower() if sale_el else ""
            ticket_status = "sold_out" if "slutsålt" in sale_text or "sold" in sale_text else "on_sale"

            ext_id = hashlib.md5(f"debaser:{artist}:{event_date}".encode()).hexdigest()[:12]

            return {
                "external_id": ext_id,
                "venue_slug": venue_slug,
                "artist": artist,
                "title": None,
                "event_date": event_date,
                "event_time": None,
                "genre": genre_text if genre_text else None,
                "ticket_url": ticket_url if ticket_url != "#" else detail_url,
                "ticket_status": ticket_status,
            }
        except Exception as e:
            print(f"  Debaser: kunde inte parsa: {e}")
            return None

    def collect(self) -> int:
        from ..db.database import upsert_event
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:debaser"
            upsert_event(**ev)
            count += 1
        return count
