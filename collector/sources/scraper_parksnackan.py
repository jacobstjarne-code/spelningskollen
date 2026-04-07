"""Scraper för Parksnäckan Uppsala (via Tickster)."""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper

BASE_URL = "https://www.tickster.com"
LISTING_URL = f"{BASE_URL}/se/sv/events/at/4fykbwf31jg29te/parksnackan"


class ParksnackanScraper(VenueScraper):
    venue_slug = "parksnackan"
    venue_url = LISTING_URL
    events_per_page = 16

    def scrape(self) -> list[dict]:
        events = []
        skip = 0

        while True:
            url = f"{self.venue_url}?skip={skip}&take={self.events_per_page}" if skip else self.venue_url
            soup = self.fetch_page(url)
            if not soup:
                break

            page_events = self._parse_page(soup)
            if not page_events:
                break

            events.extend(page_events)
            skip += self.events_per_page

            # Säkerhetsgräns
            if skip >= 100:
                break

        return events

    def _parse_page(self, soup) -> list[dict]:
        events = []

        # Event-länkar har datum i URL: /events/ID/YYYY-MM-DD/slug
        event_links = soup.select('a[href*="/events/"][href*="/202"]')

        for link in event_links:
            try:
                href = link.get("href", "")
                artist = link.get_text(strip=True)

                if not artist:
                    continue

                # Skippa presentkort och liknande
                if "presentkort" in artist.lower():
                    continue

                # Datum från URL: /events/xxx/2026-06-05/slug
                date_match = re.search(r"/(\d{4}-\d{2}-\d{2})/", href)
                if not date_match:
                    continue

                event_date = date.fromisoformat(date_match.group(1))
                if event_date < date.today():
                    continue

                # Biljettlänk — i nästa syskon-div finns en secure.tickster.com-länk
                ticket_url = None
                ticket_status = "on_sale"
                next_div = link.find_next_sibling("div")
                if next_div:
                    buy_link = next_div.select_one('a[href*="secure.tickster.com"]')
                    if buy_link:
                        ticket_url = buy_link.get("href")

                    div_text = next_div.get_text().lower()
                    if "utsålt" in div_text or "utsalt" in div_text:
                        ticket_status = "sold_out"

                # Bild
                img = link.select_one("img")
                image_url = img.get("src") if img else None

                ext_id = hashlib.md5(f"parksnackan:{artist}:{event_date}".encode()).hexdigest()[:12]

                events.append({
                    "external_id": ext_id,
                    "artist": artist,
                    "title": None,
                    "event_date": event_date,
                    "event_time": None,
                    "genre": None,
                    "image_url": image_url,
                    "ticket_url": ticket_url,
                    "ticket_status": ticket_status,
                })
            except Exception as e:
                print(f"  Parksnäckan: kunde inte parsa event: {e}")
                continue

        return events
