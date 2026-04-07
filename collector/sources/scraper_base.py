"""Baslogik för venue-scrapers."""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod
from datetime import date


class VenueScraper(ABC):
    """Basklass för venue-scrapers."""

    venue_slug: str = ""
    venue_url: str = ""
    source_prefix: str = "scraper"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Konsertkalender/1.0 (kontakt: jacob@example.com)"
        })

    @property
    def source_name(self) -> str:
        return f"{self.source_prefix}:{self.venue_slug}"

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as e:
            print(f"  Fel vid hämtning av {url}: {e}")
            return None

    @abstractmethod
    def scrape(self) -> list[dict]:
        """Returnera lista med event-dicts redo för upsert_event()."""
        ...

    def collect(self) -> int:
        from ..db.database import upsert_event
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = self.source_name
            ev["venue_slug"] = self.venue_slug
            upsert_event(**ev)
            count += 1
        return count
