"""Scraper för Fasching (fasching.se) via WordPress REST API."""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from .scraper_base import VenueScraper
from ..db.database import upsert_event

API_URL = "https://www.fasching.se/wp-json/wp/v2/posts"


class FaschingScraper(VenueScraper):
    venue_slug = "fasching"
    venue_url = "https://fasching.se/program/"

    def scrape(self) -> list[dict]:
        events = []
        page = 1

        while True:
            resp = self.session.get(API_URL, params={
                "per_page": 50,
                "page": page,
                "_embed": True,
                "orderby": "date",
                "order": "asc",
            }, timeout=15)

            if resp.status_code == 400:
                break  # Inga fler sidor
            if not resp.ok:
                print(f"  Fasching API fel: {resp.status_code}")
                break

            posts = resp.json()
            if not posts:
                break

            for post in posts:
                parsed = self._parse_post(post)
                if parsed:
                    events.extend(parsed)

            # Kolla om det finns fler sidor
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1

        return events

    def _parse_post(self, post: dict) -> list[dict]:
        """Ett post kan ha flera datum — returnera ett event per datum."""
        results = []
        try:
            artist = post.get("title", {}).get("rendered", "").strip()
            if not artist:
                return []

            # HTML-entiteter i titeln
            artist = artist.replace("&#8211;", "–").replace("&amp;", "&").replace("&#8217;", "'")

            link = post.get("link", "")

            # Bild
            image_url = None
            try:
                media = post["_embedded"]["wp:featuredmedia"][0]
                image_url = media.get("source_url")
            except (KeyError, IndexError, TypeError):
                pass

            # Datum och biljettlänkar från meta.dates
            meta = post.get("meta", {})
            dates = meta.get("dates") if isinstance(meta, dict) else None

            if not dates:
                return []

            today = date.today()

            for d in dates:
                dt_str = d.get("date_time", "")
                if not dt_str:
                    continue

                try:
                    dt = datetime.fromisoformat(dt_str)
                except ValueError:
                    continue

                if dt.date() < today:
                    continue

                ticket_url = d.get("buy_link") or meta.get("buy_link") or link
                btn_state = d.get("btn_state", "buy_ticket")
                ticket_status = "sold_out" if btn_state in ("sold_out", "soldout") else "on_sale"

                ext_id = hashlib.md5(
                    f"fasching:{artist}:{dt.date()}".encode()
                ).hexdigest()[:12]

                results.append({
                    "external_id": ext_id,
                    "venue_slug": "fasching",
                    "artist": artist,
                    "title": None,
                    "event_date": dt.date(),
                    "event_time": dt.strftime("%H:%M"),
                    "genre": None,
                    "image_url": image_url,
                    "ticket_url": ticket_url,
                    "ticket_status": ticket_status,
                })

        except Exception as e:
            print(f"  Fasching: kunde inte parsa post: {e}")

        return results

    def collect(self) -> int:
        """Override — venue_slug varierar inte men vi vill ha kontroll."""
        events = self.scrape()
        count = 0
        for ev in events:
            ev["source"] = "scraper:fasching"
            upsert_event(**ev)
            count += 1
        return count
