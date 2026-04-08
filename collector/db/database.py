"""Spelningskollen — Databaslager.

Turso (libSQL via HTTP) i produktion, SQLite lokalt.
Samma mönster som jobbagenten.
"""
from __future__ import annotations

import os
import sqlite3
import mimetypes
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, date
from typing import Optional

import requests as _http
from ..genre import normalize_genre

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────

_TURSO_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
_TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

_DATA_DIR = os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent))
DB_PATH = os.path.join(_DATA_DIR, "spelningskollen.db")


# ──────────────────────────────────────────────────────────────────────────────
# Turso HTTP-wrapper (från jobbagenten — lättviktig, sqlite3-kompatibelt)
# ──────────────────────────────────────────────────────────────────────────────

class _TursoCursor:
    """Minimal cursor som returnerar dicts."""
    def __init__(self, cols, rows, last_insert_rowid=None):
        self._rows = rows
        self._cols = cols
        self.lastrowid = last_insert_rowid
        self.rowcount = len(rows)
        self.description = [(c, None, None, None, None, None, None) for c in cols]

    def fetchall(self):
        return [dict(zip(self._cols, r)) for r in self._rows]

    def fetchone(self):
        if self._rows:
            return dict(zip(self._cols, self._rows[0]))
        return None

    def __iter__(self):
        return iter(self.fetchall())


class _TursoConnection:
    """HTTP-baserad anslutning till Turso. Efterliknar sqlite3.Connection."""
    def __init__(self, url, token):
        url = url.replace("libsql://", "https://").replace("wss://", "https://")
        self._url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def execute(self, sql, params=None):
        args = []
        if params:
            for p in params:
                if p is None:
                    args.append({"type": "null"})
                elif isinstance(p, bool):
                    args.append({"type": "integer", "value": str(int(p))})
                elif isinstance(p, int):
                    args.append({"type": "integer", "value": str(p)})
                elif isinstance(p, float):
                    args.append({"type": "float", "value": p})
                else:
                    args.append({"type": "text", "value": str(p)})

        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": args}},
                {"type": "close"},
            ]
        }

        resp = _http.post(f"{self._url}/v2/pipeline", headers=self._headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        result = data.get("results", [{}])[0]
        if result.get("type") == "error":
            err = result.get("error", {})
            raise sqlite3.OperationalError(err.get("message", "Turso error"))

        response = result.get("response", {}).get("result", {})
        cols = [c["name"] for c in response.get("cols", [])]
        raw_rows = response.get("rows", [])
        rows = []
        for raw_row in raw_rows:
            row = []
            for cell in raw_row:
                if cell.get("type") == "null":
                    row.append(None)
                elif cell.get("type") == "integer":
                    row.append(int(cell["value"]))
                elif cell.get("type") == "float":
                    row.append(float(cell["value"]))
                else:
                    row.append(cell.get("value"))
            rows.append(row)

        last_id = response.get("last_insert_rowid")
        return _TursoCursor(cols, rows, last_id)

    def executescript(self, sql):
        """Kör flera SQL-satser (används av init_db)."""
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            self.execute(stmt)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Anslutning
# ──────────────────────────────────────────────────────────────────────────────

def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def get_db():
    """Context manager för databasanslutning."""
    if _TURSO_URL and _TURSO_TOKEN:
        conn = _TursoConnection(_TURSO_URL, _TURSO_TOKEN)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """Legacy-funktion — returnerar en rå connection (använd get_db() istället)."""
    if _TURSO_URL and _TURSO_TOKEN:
        return _TursoConnection(_TURSO_URL, _TURSO_TOKEN)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Init & seed
# ──────────────────────────────────────────────────────────────────────────────

_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN canonical_id INTEGER REFERENCES events(id)",
    "ALTER TABLE events ADD COLUMN status TEXT DEFAULT 'active'",
    "ALTER TABLE events ADD COLUMN local_image_path TEXT",
    "ALTER TABLE user_lists ADD COLUMN share_token TEXT",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_lists_share_token ON user_lists(share_token)",
    "CREATE INDEX IF NOT EXISTS idx_events_canonical ON events(canonical_id)",
]


def init_db():
    """Skapa tabeller och kör migreringar."""
    schema_path = Path(__file__).parent / "schema.sql"
    if _TURSO_URL and _TURSO_TOKEN:
        conn = _TursoConnection(_TURSO_URL, _TURSO_TOKEN)
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = _dict_factory

    with open(schema_path) as f:
        conn.executescript(f.read())

    # Idempotenta migreringar
    for migration in _MIGRATIONS:
        try:
            conn.execute(migration)
        except Exception:
            pass  # Kolumn/tabell finns redan

    conn.close()


def seed_venue_aliases():
    """Seeda venue_aliases-tabellen. Kallas automatiskt av seed_venues()."""
    from ..venue_resolver import seed_venue_aliases as _seed
    return _seed()


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
    # Seeda alias-tabellen (idempotent)
    seed_venue_aliases()


# ──────────────────────────────────────────────────────────────────────────────
# Event-operationer
# ──────────────────────────────────────────────────────────────────────────────

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
    # Normalisera genre: råvärde → subgenre, normaliserat → genre
    normalized = normalize_genre(genre)
    raw_subgenre = subgenre or genre  # Behåll råvärdet som subgenre

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
               subgenre = excluded.subgenre,
               ticket_url = excluded.ticket_url,
               ticket_status = excluded.ticket_status,
               price_min = excluded.price_min,
               price_max = excluded.price_max,
               image_url = excluded.image_url,
               last_updated = CURRENT_TIMESTAMP""",
        (source, external_id, venue_id, artist, title, str(event_date), event_time,
         doors_open, normalized, raw_subgenre, description, image_url, ticket_url,
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


def migrate_genres():
    """Engångsmigrering: normalisera genre-fältet för befintliga events."""
    conn = get_connection()
    events = conn.execute("SELECT id, genre FROM events WHERE genre IS NOT NULL").fetchall()
    updated = 0
    for e in events:
        raw = e["genre"]
        normalized = normalize_genre(raw)
        if normalized != raw:  # Undvik onödiga skrivningar
            conn.execute(
                "UPDATE events SET subgenre = genre, genre = ? WHERE id = ?",
                (normalized, e["id"])
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"migrate_genres: {updated} events uppdaterade")
    return updated


def migrate_fix_encoding():
    """Engångsmigrering: rensa HTML-entities och unicode-fel i befintlig data."""
    from ..text_utils import clean_text
    conn = get_connection()
    events = conn.execute(
        "SELECT id, artist, title, description FROM events"
    ).fetchall()
    updated = 0
    for e in events:
        updates: dict = {}
        for field in ["artist", "title", "description"]:
            original = e[field]
            if original:
                cleaned = clean_text(original)
                if cleaned != original:
                    updates[field] = cleaned
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE events SET {set_clause} WHERE id = ?",
                list(updates.values()) + [e["id"]]
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"migrate_fix_encoding: {updated} events uppdaterade")
    return updated


def migrate_strip_dates_from_titles():
    """Engångsmigrering: ta bort datum-mönster ur event-titlar."""
    from ..text_utils import strip_date_from_title
    conn = get_connection()
    events = conn.execute(
        "SELECT id, title FROM events WHERE title IS NOT NULL"
    ).fetchall()
    updated = 0
    for e in events:
        stripped = strip_date_from_title(e["title"])
        if stripped != e["title"]:
            conn.execute(
                "UPDATE events SET title = ? WHERE id = ?",
                (stripped or None, e["id"])
            )
            updated += 1
    conn.commit()
    conn.close()
    print(f"migrate_strip_dates_from_titles: {updated} titlar uppdaterade")
    return updated


if __name__ == "__main__":
    init_db()
    seed_venues()
    print("Databas initierad med venues.")
