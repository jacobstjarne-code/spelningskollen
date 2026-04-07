"""Scraper för Katalin Uppsala (katalin.com/events/)."""
from __future__ import annotations

import re
import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper

MONTHS_SV = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10,
    "november": 11, "december": 12,
}


class KatalinScraper(VenueScraper):
    venue_slug = "katalin"
    venue_url = "https://www.katalin.com/events/"

    def scrape(self) -> list[dict]:
        events = []
        for tab in range(1, 10):
            url = self.venue_url if tab == 1 else f"{self.venue_url}?tab={tab}"
            soup = self.fetch_page(url)
            if not soup:
                break

            items = soup.select(".events__list-item")
            if not items:
                break

            for item in items:
                parsed = self._parse_item(item)
                if parsed:
                    events.append(parsed)

            # Kolla om det finns nästa sida
            next_link = soup.select_one(f'a.page-numbers[href*="tab={tab+1}"]')
            if not next_link:
                break

        return events

    def _parse_item(self, item) -> dict | None:
        try:
            # Artist — texten i item__content-länken, exkl genre/datum/etc
            content_link = item.select_one("a.item__content")
            if not content_link:
                return None

            # Artistnamn sitter direkt i länken, inte i en span
            # Hämta all text, ta bort genre/datum-delarna
            genre_el = item.select_one(".item__content-genre")
            genre = genre_el.get_text(strip=True) if genre_el else None

            # Hämta textnoder direkt under a.item__content
            artist = ""
            for child in content_link.children:
                if isinstance(child, str):
                    t = child.strip()
                    if t:
                        artist = t
                        break
                elif hasattr(child, 'name') and child.name is None:
                    t = child.strip()
                    if t:
                        artist = t
                        break

            # Fallback: full text minus kända delar
            if not artist:
                full_text = content_link.get_text(" | ", strip=True)
                parts = [p.strip() for p in full_text.split("|")]
                # Ta bort genre, datum, tid, scen, beskrivning
                for p in parts:
                    if p == genre:
                        continue
                    if re.match(r"^\d{1,2}:\d{2}$", p):
                        continue
                    if any(m in p.lower() for m in MONTHS_SV.keys()):
                        continue
                    if p.lower() in ("jazzbaren", "puben", "stora scen", "terassen"):
                        continue
                    if len(p) > 5:
                        artist = p
                        break

            if not artist:
                return None

            # Datum
            date_el = item.select_one(".info__date")
            event_date = None
            if date_el:
                event_date = self._parse_swedish_date(date_el.get_text(strip=True))

            if not event_date or event_date < date.today():
                return None

            # Tid
            time_el = item.select_one(".info__time")
            event_time = time_el.get_text(strip=True) if time_el else None

            # Biljettlänk
            ticket_el = item.select_one("a.gtm-ticket, a[href*='tickster.com'], a[href*='ticket']")
            ticket_url = ticket_el.get("href") if ticket_el else None

            # Bild
            img_div = item.select_one(".item__image")
            image_url = None
            if img_div:
                style = img_div.get("style", "")
                m = re.search(r"url\('([^']+)'\)", style)
                if m:
                    image_url = m.group(1)

            ext_id = hashlib.md5(f"katalin:{artist}:{event_date}".encode()).hexdigest()[:12]

            return {
                "external_id": ext_id,
                "artist": artist,
                "title": None,
                "event_date": event_date,
                "event_time": event_time,
                "genre": genre,
                "image_url": image_url,
                "ticket_url": ticket_url,
                "ticket_status": "on_sale" if ticket_url else "unknown",
            }
        except Exception as e:
            print(f"  Katalin: kunde inte parsa: {e}")
            return None

    def _parse_swedish_date(self, text: str) -> date | None:
        """Parsa 'Tisdag 7 april' → date(2026, 4, 7)."""
        text = text.lower().strip()
        match = re.search(r"(\d{1,2})\s+(\w+)", text)
        if not match:
            return None
        day = int(match.group(1))
        month_str = match.group(2)
        month = MONTHS_SV.get(month_str)
        if not month:
            return None
        year = date.today().year
        try:
            d = date(year, month, day)
            if d < date.today():
                d = date(year + 1, month, day)
            return d
        except ValueError:
            return None
