"""Baslogik för venue-scrapers."""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod
from datetime import date
from ..text_utils import clean_text, clean_event_title


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
            # Ge BeautifulSoup råa bytes — den detekterar charset från <meta> taggar
            # istf att förlita sig på HTTP Content-Type-headern som ofta är fel.
            return BeautifulSoup(resp.content, "html.parser")
        except requests.RequestException as e:
            print(f"  Fel vid hämtning av {url}: {e}")
            return None

    def clean(self, text: str | None) -> str | None:
        """Rensa text — HTML-entities, unicode, whitespace."""
        return clean_text(text)

    def clean_title(self, text: str | None) -> str | None:
        """Rensa titel och ta bort datum-mönster."""
        return clean_event_title(text)

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
