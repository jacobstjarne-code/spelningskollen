"""Databashantering för konsertkalendern."""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from datetime import datetime, date
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent.parent / "konsertkalender.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Skapa tabeller om de inte finns."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_connection()
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()


def seed_venues():
    """Lägg in kända venues om de inte redan finns."""
    venues = [
        # Stora scener Stockholm
        ("Avicii Arena", "Stockholm", "avicii-arena", "arena", "https://www.aviciiarena.se", 16000),
        ("Tele2 Arena", "Stockholm", "tele2-arena", "arena", "https://www.tele2arena.se", 33000),
        ("Strawberry Arena", "Stockholm", "strawberry-arena", "arena", "https://www.strawberryarena.se", 30000),
        ("Gröna Lund", "Stockholm", "grona-lund", "outdoor", "https://www.gronalund.com", 5000),
        ("Skansen Solliden", "Stockholm", "skansen-solliden", "outdoor", "https://www.skansen.se", 2600),
        ("Cirkus", "Stockholm", "cirkus", "arena", "https://www.cirkus.se", 1800),
        ("Annexet", "Stockholm", "annexet", "arena", "https://www.aviciiarena.se", 4000),
        # Klubbar Stockholm
        ("Nalen", "Stockholm", "nalen", "club", "https://www.nalen.com", 800),
        ("Slaktkyrkan", "Stockholm", "slaktkyrkan", "club", "https://www.slfrk.com", 600),
        ("Södra Teatern", "Stockholm", "sodra-teatern", "club", "https://www.sodrateatern.com", 550),
        ("Under Bron", "Stockholm", "under-bron", "club", "https://www.underbron.se", 450),
        ("Debaser Strand", "Stockholm", "debaser-strand", "club", "https://www.debaser.se", 500),
        ("Berns", "Stockholm", "berns", "club", "https://www.berns.se", 1200),
        ("Münchenbryggeriet", "Stockholm", "munchenbryggeriet", "club", "https://www.munchenbryggeriet.se", 1500),
        ("Fasching", "Stockholm", "fasching", "club", "https://www.fasching.se", 350),
        ("Fållan", "Stockholm", "fallan", "club", None, 300),
        ("Hus 7", "Stockholm", "hus-7", "club", "https://www.hus7.se", 400),
        ("Bryggarsalen", "Stockholm", "bryggarsalen", "club", "https://www.bryggarsalen.se", 250),
        ("Kraken", "Stockholm", "kraken", "club", "https://www.kfrk.se", 300),
        ("Orionteatern", "Stockholm", "orionteatern", "club", "https://www.orionteatern.se", 200),
        # Uppsala
        ("Katalin", "Uppsala", "katalin", "club", "https://www.katalin.com", 550),
        ("Flustret", "Uppsala", "flustret", "club", "https://www.flustret.se", 400),
        ("Parksnäckan", "Uppsala", "parksnackan", "outdoor", None, 3000),
        ("Botaniska", "Uppsala", "botaniska", "outdoor", None, 5000),
        ("IFU Arena", "Uppsala", "ifu-arena", "arena", None, 8500),
        ("Uppsala Konsert & Kongress", "Uppsala", "ukk", "arena", "https://www.ukk.se", 1200),
    ]

    conn = get_connection()
    for name, city, slug, vtype, url, cap in venues:
        conn.execute(
            """INSERT OR IGNORE INTO venues (name, city, slug, venue_type, website_url, capacity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, city, slug, vtype, url, cap),
        )
    conn.commit()
    conn.close()


def upsert_event(
    source: str,
    external_id: str,
    venue_slug: str | None,
    artist: str,
    title: str | None,
    event_date: date,
    event_time: str | None = None,
    doors_open: str | None = None,
    genre: str | None = None,
    subgenre: str | None = None,
    description: str | None = None,
    image_url: str | None = None,
    ticket_url: str | None = None,
    ticket_status: str = "unknown",
    price_min: float | None = None,
    price_max: float | None = None,
    on_sale_date: str | None = None,
) -> int:
    """Lägg in eller uppdatera ett event. Returnerar event-ID."""
    conn = get_connection()

    venue_id = None
    if venue_slug:
        row = conn.execute("SELECT id FROM venues WHERE slug = ?", (venue_slug,)).fetchone()
        if row:
            venue_id = row["id"]

    conn.execute(
        """INSERT INTO events (source, external_id, venue_id, artist, title, date, time,
                               doors_open, genre, subgenre, description, image_url, ticket_url,
                               ticket_status, price_min, price_max, on_sale_date, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(source, external_id) DO UPDATE SET
               artist = excluded.artist,
               title = excluded.title,
               date = excluded.date,
               time = excluded.time,
               genre = excluded.genre,
               ticket_url = excluded.ticket_url,
               ticket_status = excluded.ticket_status,
               price_min = excluded.price_min,
               price_max = excluded.price_max,
               image_url = excluded.image_url,
               last_updated = CURRENT_TIMESTAMP""",
        (source, external_id, venue_id, artist, title, str(event_date), event_time,
         doors_open, genre, subgenre, description, image_url, ticket_url,
         ticket_status, price_min, price_max, on_sale_date),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id FROM events WHERE source = ? AND external_id = ?",
        (source, external_id),
    ).fetchone()
    event_id = row["id"]
    conn.close()
    return event_id


def get_upcoming_events(city: str | None = None, days_ahead: int = 90) -> list[dict]:
    """Hämta kommande events, valfritt filtrerat på stad."""
    conn = get_connection()
    query = """
        SELECT e.*, v.name as venue_name, v.city, v.slug as venue_slug, v.venue_type
        FROM events e
        LEFT JOIN venues v ON e.venue_id = v.id
        WHERE e.date >= date('now')
          AND e.date <= date('now', '+' || ? || ' days')
    """
    params: list = [days_ahead]

    if city:
        query += " AND v.city = ?"
        params.append(city)

    query += " ORDER BY e.date, e.time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    seed_venues()
    print("Databas initierad med venues.")
