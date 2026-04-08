"""Huvudskript för konsertkalender-insamling.

Kör alla datakällor och sparar till SQLite.
Användning:
    python -m collector.main              # Kör allt
    python -m collector.main --source tm  # Bara Ticketmaster
    python -m collector.main --source sk  # Bara Songkick
    python -m collector.main --source sc  # Bara scrapers
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Lägg till projektrot i path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from collector.db.database import init_db, seed_venues
from collector.sources import ticketmaster, bandsintown, resident_advisor, allthingslive
from collector.sources.scraper_tickster import TicksterScraper
from collector.sources.scraper_fasching import FaschingScraper
from collector.sources.scraper_munchenbryggeriet import MunchenbryggerietScraper
from collector.sources.scraper_stockholmlive import StockholmLiveScraper
from collector.sources.scraper_debaser import DebaserScraper
from collector.sources.scraper_katalin import KatalinScraper
from collector.sources.scraper_parksnackan import ParksnackanScraper
from collector.sources.scraper_luger import LugerScraper
from collector.sources.scraper_kaliber import KaliberScraper
from collector.sources.scraper_nalen import NalenScraper
from collector.sources.scraper_sodrateatern import SodraTeaternScraper


ALL_SCRAPERS = [
    TicksterScraper,              # Nalen, Berns, Debaser, Fållan, Orionteatern, Flustret, m.fl.
    FaschingScraper,              # Fasching (WordPress REST API)
    MunchenbryggerietScraper,     # Münchenbryggeriet
    StockholmLiveScraper,         # Avicii Arena, Annexet, Strawberry Arena
    DebaserScraper,
    KatalinScraper,
    ParksnackanScraper,
    LugerScraper,
    KaliberScraper,
    NalenScraper,                 # nalen.com direkt (kompletterar Tickster)
    SodraTeaternScraper,          # sodrateatern.com — musik-show-filter
]


def run_scrapers() -> int:
    """Kör alla venue-scrapers."""
    total = 0
    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        print(f"Scraper: {scraper.venue_slug}...")
        try:
            count = scraper.collect()
            print(f"  {count} events sparade")
            total += count
        except Exception as e:
            print(f"  FEL: {e}")
    return total


def main():
    parser = argparse.ArgumentParser(description="Konsertkalender — datainsamling")
    parser.add_argument("--source", choices=["tm", "sc", "all"], default="all",
                        help="Datakälla: tm=Ticketmaster, sc=Scrapers, all=Alla")
    parser.add_argument("--init", action="store_true", help="Initiera databas och venues")
    args = parser.parse_args()

    print(f"=== Konsertkalender insamling — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    # Alltid initiera DB (idempotent)
    init_db()
    if args.init:
        seed_venues()
        print("Databas och venues initierade.\n")

    total = 0

    if args.source in ("tm", "all"):
        total += ticketmaster.collect()
        print()

    if args.source in ("sc", "all"):
        for label, fn in [("Bandsintown", bandsintown.collect), ("Resident Advisor", resident_advisor.collect), ("All Things Live", allthingslive.collect)]:
            try:
                n = fn()
                print(f"{label}: {n} events")
                total += n
            except Exception as e:
                print(f"{label}: FEL — {e}")
        print()

    if args.source in ("sc", "all"):
        total += run_scrapers()
        print()

    print(f"=== Klart! Totalt {total} events insamlade ===")


if __name__ == "__main__":
    main()
