"""Generisk Tickster-scraper — kör flera venues via tickster.com.

Tickster säljer biljetter åt Nalen, Södra Teatern, Fållan, Orionteatern,
Flustret, Kulturhuset, Berns, Slaktkyrkan, Gröna Lund, Debaser m.fl.

HTML-struktur: .c-tile per event.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date
from urllib.parse import quote
from .scraper_base import VenueScraper
from ..db.database import upsert_event

# Tickster URL-slug → vår venue-slug
TICKSTER_VENUES = {
    "nalen":          "nalen",
    "berns":          "berns",
    "debaser":        "debaser-strand",
    "slaktkyrkan":    "slaktkyrkan",
    "orionteatern":   "orionteatern",
    "f%C3%A5llan":    "fallan",
    "gr%C3%B6na-lund": "grona-lund",
    "flustret":       "flustret",
    "cirkus":         "cirkus",
}

# Skippa icke-musik events
SKIP_KEYWORDS = ["presentkort", "julbord", "brunch", "restaurang", "barnteater"]

BASE_URL = "https://www.tickster.com"
EVENTS_PER_PAGE = 16


class TicksterScraper(VenueScraper):
    """Scrapar alla konfigurerade venues från Tickster."""
    venue_slug = "nalen"
    venue_url = BASE_URL

    def scrape(self) -> list[dict]:
        all_events: list[dict] = []
        for tickster_slug, our_slug in TICKSTER_VENUES.items():
            events = self._scrape_venue(tickster_slug, our_slug)
            all_events.extend(events)
        return all_events

    def _scrape_venue(self, tickster_slug: str, our_slug: str) -> list[dict]:
        events: list[dict] = []
        skip = 0
        while True:
            url = f"{BASE_URL}/se/sv/events/at/{tickster_slug}"
            if skip:
                url += f"?skip={skip}&take={EVENTS_PER_PAGE}&sort=eventstart"
            soup = self.fetch_page(url)
            if not soup:
                break
            page_events = self._parse_page(soup, our_slug)
            if not page_events:
                break
            events.extend(page_events)
            # Finns fler sidor?
            if soup.select_one(f'a[href*="skip={skip + EVENTS_PER_PAGE}"]'):
                skip += EVENTS_PER_PAGE
                if skip >= 200:
                    break
            else:
                break
        return events

    def _parse_page(self, soup, our_slug: str) -> list[dict]:
        events: list[dict] = []
        for tile in soup.select(".c-tile"):
            ev = self._parse_tile(tile, our_slug)
            if ev:
                events.append(ev)
        return events

    def _parse_tile(self, tile, our_slug: str) -> dict | None:
        try:
            head = tile.select_one(".c-tile__head")
            if not head:
                return None

            # Datum ur URL: /se/sv/events/xxx/2026-04-09/slug
            href = head.get("href", "")
            date_match = re.search(r"/(\d{4}-\d{2}-\d{2})/", href)
            if not date_match:
                return None
            event_date = date.fromisoformat(date_match.group(1))
            if event_date < date.today():
                return None

            # Artist/titel — .c-tile__title kan ha inbäddad whitespace
            title_el = tile.select_one(".c-tile__title")
            if not title_el:
                return None
            artist = re.sub(r"\s+", " ", title_el.get_text()).strip()
            if not artist:
                return None

            # Filtrera bort icke-musik
            lower = artist.lower()
            if any(kw in lower for kw in SKIP_KEYWORDS):
                return None

            # Biljettknapp
            btn = tile.select_one(".c-button--primary, .c-button")
            ticket_url = None
            ticket_status = "on_sale"
            if btn:
                btn_text = btn.get_text(strip=True).lower()
                if "utsålt" in btn_text or "sold out" in btn_text:
                    ticket_status = "sold_out"
                else:
                    ticket_url = btn.get("href") or None

            # Bild
            img = tile.select_one("img")
            image_url = None
            if img:
                image_url = img.get("data-src") or img.get("src") or None

            ext_id = hashlib.md5(
                f"tickster:{our_slug}:{artist}:{event_date}".encode()
            ).hexdigest()[:12]

            return {
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
            }
        except Exception as e:
            print(f"  Tickster/{our_slug}: parse-fel: {e}")
            return None

    def collect(self) -> int:
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:tickster"
            upsert_event(**ev)
            count += 1
        return count
