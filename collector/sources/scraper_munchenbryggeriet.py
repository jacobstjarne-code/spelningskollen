"""Scraper för Münchenbryggeriet (munchenbryggeriet.se).

Två-fas-scraping: listar events på /publika-evenemang/, hämtar
sedan datuminfo från varje event-sida.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper
from ..db.database import upsert_event

BASE_URL = "https://munchenbryggeriet.se"
LISTING_URL = f"{BASE_URL}/publika-evenemang/"

MONTHS_SV = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


class MunchenbryggerietScraper(VenueScraper):
    venue_slug = "munchenbryggeriet"
    venue_url = LISTING_URL

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(LISTING_URL)
        if not soup:
            return []

        events = []
        today = date.today()

        # Alla event-länkare på listsidan — <a href="/event/.../">
        links = soup.select('a[href*="/event/"]')
        seen_hrefs = set()

        for link in links:
            href = link.get("href", "")
            if not href or href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            full_url = href if href.startswith("http") else BASE_URL + href

            # Datum från listsidan: <p>Evenemang YYYY-MM-DD</p>
            date_el = link.select_one("p")
            event_date = None
            if date_el:
                date_text = date_el.get_text(strip=True)
                m = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
                if m:
                    try:
                        event_date = date.fromisoformat(m.group(1))
                    except ValueError:
                        pass

            if event_date and event_date < today:
                continue

            # Titel från <h4> eller <h3>
            title_el = link.select_one("h4") or link.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""

            # Bild
            img_el = link.select_one("img")
            image_url = img_el.get("src") if img_el else None

            # Om vi saknar datum eller titel — hämta event-sida
            # Hämta detaljsida för biljettlänk och ev. saknad info
            detail = self._fetch_detail(full_url)
            if detail:
                event_date = event_date or detail.get("date")
                title = title or detail.get("title", "")
                image_url = image_url or detail.get("image_url")

            if not event_date or not title or event_date < today:
                continue

            ticket_url = (detail.get("ticket_url") if detail else None) or full_url

            ext_id = hashlib.md5(
                f"munchen:{title}:{event_date}".encode()
            ).hexdigest()[:12]

            events.append({
                "external_id": ext_id,
                "venue_slug": self.venue_slug,
                "artist": title,
                "title": None,
                "event_date": event_date,
                "event_time": None,
                "genre": None,
                "image_url": image_url,
                "ticket_url": ticket_url,
                "ticket_status": "on_sale",
            })

        return events

    def _fetch_detail(self, url: str) -> dict | None:
        """Hämta titel, datum och biljettlänk från event-sida."""
        soup = self.fetch_page(url)
        if not soup:
            return None

        result: dict = {}
        today = date.today()

        # Titel
        h1 = soup.select_one("h1")
        if h1:
            result["title"] = h1.get_text(strip=True)

        # Bild (hero/header img)
        img = soup.select_one(".header img, article img, .wp-block-image img, img[src*='uploads']")
        if img:
            result["image_url"] = img.get("src")

        # Datum — "Lör 9 maj 2026" eller "YYYY-MM-DD"
        page_text = soup.get_text(" ")
        # ISO-format
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", page_text)
        if m:
            try:
                result["date"] = date.fromisoformat(m.group(1))
            except ValueError:
                pass

        # "Lör 9 maj 2026" format
        if "date" not in result:
            m2 = re.search(
                r"\b(?:mån|tis|ons|tor|fre|lör|sön)\s+(\d{1,2})\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)\s+(\d{4})\b",
                page_text,
                re.IGNORECASE
            )
            if m2:
                day = int(m2.group(1))
                month = MONTHS_SV.get(m2.group(2).lower())
                year = int(m2.group(3))
                if month:
                    try:
                        result["date"] = date(year, month, day)
                    except ValueError:
                        pass

        # Biljettlänk — Ticketmaster, Billetto, Nortic etc.
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if any(t in href for t in ["ticketmaster", "billetto", "nortic", "secure.tickster"]):
                result["ticket_url"] = href
                break

        return result if result else None

    def collect(self) -> int:
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:munchenbryggeriet"
            upsert_event(**ev)
            count += 1
        return count
