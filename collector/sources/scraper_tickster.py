"""Generisk Tickster-scraper — kör flera venues via tickster.com.

Tickster säljer biljetter åt Nalen, Södra Teatern, Fållan, Orionteatern,
Flustret, Kulturhuset, Berns, Slaktkyrkan, Gröna Lund, Debaser m.fl.
Samma HTML-struktur som Parksnäckan-scrapern.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date
from .scraper_base import VenueScraper
from ..db.database import upsert_event

# Tickster-slug → vår venue-slug
TICKSTER_VENUES = {
    "nalen": "nalen",
    "södra-teatern": "sodra-teatern",
    "berns": "berns",
    "debaser": "debaser-strand",
    "slaktkyrkan": "slaktkyrkan",
    "orionteatern": "orionteatern",
    "fållan": "fallan",
    "gröna-lund": "grona-lund",
    "flustret": "flustret",
    "kulturhuset-stadsteatern": "cirkus",  # Placeholder — lägg till venue om du vill
}

BASE_URL = "https://www.tickster.com"
EVENTS_PER_PAGE = 16


class TicksterScraper(VenueScraper):
    """Scrapar alla konfigurerade venues från Tickster."""
    venue_slug = "nalen"  # Default, men varierar
    venue_url = BASE_URL

    def scrape(self) -> list[dict]:
        """Returnerar alla events från alla Tickster-venues."""
        all_events = []
        for tickster_slug, our_slug in TICKSTER_VENUES.items():
            events = self._scrape_venue(tickster_slug, our_slug)
            all_events.extend(events)
        return all_events

    def _scrape_venue(self, tickster_slug: str, our_slug: str) -> list[dict]:
        events = []
        skip = 0

        while True:
            url = f"{BASE_URL}/se/sv/events/at/{tickster_slug}"
            if skip:
                url += f"?skip={skip}&take={EVENTS_PER_PAGE}&sort=eventstart"

            soup = self.fetch_page(url)
            if not soup:
                break

            page_events = self._parse_page(soup, tickster_slug, our_slug)
            if not page_events:
                break

            events.extend(page_events)
            skip += EVENTS_PER_PAGE

            # Kolla om det finns fler sidor
            next_link = soup.select_one(f'a[href*="skip="]')
            if not next_link or skip >= 200:
                break

        return events

    def _parse_page(self, soup, tickster_slug: str, our_slug: str) -> list[dict]:
        events = []
        event_links = soup.select('a[href*="/events/"][href*="/202"]')

        for link in event_links:
            try:
                href = link.get("href", "")
                artist = link.get_text(strip=True)

                if not artist:
                    continue

                # Skippa presentkort, jazzbrunch-generics etc.
                lower = artist.lower()
                if any(skip in lower for skip in ["presentkort", "julbord", "brunch"]):
                    continue

                # Datum från URL: /events/xxx/2026-06-05/slug
                date_match = re.search(r"/(\d{4}-\d{2}-\d{2})/", href)
                if not date_match:
                    continue

                event_date = date.fromisoformat(date_match.group(1))
                if event_date < date.today():
                    continue

                # Biljettlänk + info från syskon-div
                ticket_url = None
                ticket_status = "on_sale"
                next_div = link.find_next_sibling("div")
                if next_div:
                    buy_link = next_div.select_one('a[href*="secure.tickster.com"]')
                    if buy_link:
                        ticket_url = buy_link.get("href")
                    div_text = next_div.get_text().lower()
                    if "utsålt" in div_text or "sold" in div_text:
                        ticket_status = "sold_out"

                # Bild
                img = link.select_one("img")
                image_url = img.get("src") if img else None

                ext_id = hashlib.md5(
                    f"tickster:{tickster_slug}:{artist}:{event_date}".encode()
                ).hexdigest()[:12]

                events.append({
                    "external_id": ext_id,
                    "venue_slug": our_slug,
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
                print(f"  Tickster/{tickster_slug}: kunde inte parsa: {e}")
                continue

        return events

    def collect(self) -> int:
        """Override — varje event kan ha olika venue_slug."""
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:tickster"
            upsert_event(**ev)
            count += 1
        return count
