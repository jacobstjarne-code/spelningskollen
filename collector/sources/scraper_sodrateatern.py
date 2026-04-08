"""Scraper för Södra Teatern (sodrateatern.com).

Södra Teatern kör WordPress med eventadmin.stockholmlive.com som datakälla.
47 events renderas server-side på /evenemang.

Struktur:
- .card-event    — event-kort container
- h3             — titel
- .dates         — "8 april – 9 april 2026" (tar första datum)
- a.href         — länk till event (används som biljettlänk)
- URL-sökväg     — /evenemang/{kategori}/{slug}/ — används för genre-filtrering

Filtrering: Vi inkluderar bara events med musik-relaterad kategori i URL:n
(musik-show, jazz, rock etc.), inte teater/humor/samtal.
"""
from __future__ import annotations

import re
import hashlib
from datetime import date
from .scraper_base import VenueScraper
from ..db.database import upsert_event

EVENTS_URL = "https://www.sodrateatern.com/evenemang"

# Kategorier i URL-sökvägen som räknas som musik
MUSIC_CATEGORIES = {"musik-show", "rock", "pop", "jazz", "hiphop", "elektronisk", "klassisk", "folk", "country"}

MONTHS_SV = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _parse_first_date(dates_text: str) -> date | None:
    """
    Parsa första datum ur '8 april – 9 april 2026' eller '11 april 2026'.
    """
    # Ta texten fram till " –" eller slut
    part = re.split(r"\s*[–—-]\s*", dates_text)[0].strip().lower()

    # DD MMMM YYYY
    m = re.match(r"(\d{1,2})\s+([a-zåäö]+)\s+(\d{4})", part)
    if m:
        day   = int(m.group(1))
        month = MONTHS_SV.get(m.group(2))
        year  = int(m.group(3))
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass

    # DD MMMM (utan år — ta innevarande/nästa år)
    m = re.match(r"(\d{1,2})\s+([a-zåäö]+)", part)
    if m:
        day   = int(m.group(1))
        month = MONTHS_SV.get(m.group(2))
        if month:
            today = date.today()
            for yr in (today.year, today.year + 1):
                try:
                    d = date(yr, month, day)
                    if d >= today:
                        return d
                except ValueError:
                    pass
    return None


def _is_music_event(href: str) -> bool:
    """Returnera True om URL:n tillhör en musikrelaterad kategori."""
    # /evenemang/{kategori}/{slug}/
    m = re.search(r"/evenemang/([^/]+)/", href)
    if not m:
        return True  # Okänd kategori — inkludera
    category = m.group(1).lower()
    return any(mc in category for mc in MUSIC_CATEGORIES)


class SodraTeaternScraper(VenueScraper):
    venue_slug = "sodra-teatern"
    venue_url  = EVENTS_URL

    def scrape(self) -> list[dict]:
        soup = self.fetch_page(EVENTS_URL)
        if not soup:
            return []

        events: list[dict] = []
        for card in soup.select(".card-event"):
            ev = self._parse_card(card)
            if ev:
                events.append(ev)
        return events

    def _parse_card(self, card) -> dict | None:
        try:
            link  = card.select_one("a[href]")
            title = card.select_one("h3")
            dates = card.select_one(".dates")

            if not link or not title or not dates:
                return None

            href   = link.get("href", "")
            artist = self.clean(title.get_text(strip=True))
            if not artist:
                return None

            # Ta bara musikevenemang
            if not _is_music_event(href):
                return None

            # Filtrera bort framflyttade/inställda i titeln
            lower = artist.lower()
            if "framflyttat" in lower or "inställt" in lower or "cancelled" in lower:
                return None

            event_date = _parse_first_date(dates.get_text(strip=True))
            if not event_date or event_date < date.today():
                return None

            # Utsålt-check
            ticket_status = "on_sale"
            card_text = card.get_text().lower()
            if "utsålt" in card_text or "sold out" in card_text:
                ticket_status = "sold_out"

            # Bild
            img = card.select_one("img[data-lazy-src], img[src]")
            image_url = None
            if img:
                image_url = img.get("data-lazy-src") or img.get("src")
                if image_url and "svg" in image_url.lower():
                    image_url = None

            # Genre från URL-kategori
            m = re.search(r"/evenemang/([^/]+)/", href)
            genre = m.group(1).replace("-", " ") if m else None

            ext_id = hashlib.md5(
                f"sodrateatern:{artist}:{event_date}".encode()
            ).hexdigest()[:12]

            return {
                "external_id":   ext_id,
                "artist":        artist,
                "title":         None,
                "event_date":    event_date,
                "event_time":    None,
                "genre":         genre,
                "image_url":     image_url,
                "ticket_url":    href,
                "ticket_status": ticket_status,
            }
        except Exception as e:
            print(f"  Södra Teatern: parse-fel: {e}")
            return None

    def collect(self) -> int:
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"]     = "scraper:sodrateatern"
            ev["venue_slug"] = self.venue_slug
            upsert_event(**ev)
            count += 1
        return count
