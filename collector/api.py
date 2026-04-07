"""Spelningskollen — API + statisk filserver.

Serverar:
  /api/*  → JSON API (events, venues, user lists)
  /*      → Statiska filer från Next.js export (web/out/)

Körs som: python -m collector.api
"""
from __future__ import annotations

import json
import os
import mimetypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from .db.database import get_connection, init_db, seed_venues

STATIC_DIR = Path(__file__).parent.parent / "web" / "out"

# Insamlingsintervall (sekunder). Default: var 6:e timme.
COLLECT_INTERVAL = int(os.environ.get("COLLECT_INTERVAL", 6 * 3600))


def _run_full_collect():
    """Kör alla datakällor."""
    from .sources import ticketmaster
    from .sources.scraper_debaser import DebaserScraper
    from .sources.scraper_katalin import KatalinScraper
    from .sources.scraper_parksnackan import ParksnackanScraper
    from .sources.scraper_luger import LugerScraper

    total = 0
    for label, fn in [
        ("Ticketmaster", ticketmaster.collect),
        ("Debaser", lambda: DebaserScraper().collect()),
        ("Katalin", lambda: KatalinScraper().collect()),
        ("Parksnäckan", lambda: ParksnackanScraper().collect()),
        ("Luger", lambda: LugerScraper().collect()),
    ]:
        try:
            n = fn()
            print(f"[Collect] {label}: {n} events")
            total += n
        except Exception as e:
            print(f"[Collect] {label}: FEL — {e}")
    print(f"[Collect] Klart: {total} events totalt")
    return total


def _schedule_collect():
    """Kör insamling i bakgrunden med fast intervall."""
    def loop():
        import time
        while True:
            time.sleep(COLLECT_INTERVAL)
            print(f"[Cron] Startar schemalagd insamling...")
            try:
                _run_full_collect()
            except Exception as e:
                print(f"[Cron] Fel: {e}")
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    print(f"  Schemalagd insamling var {COLLECT_INTERVAL // 3600}h")

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}


class APIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # API-routes
        api_routes = {
            "/api/events": self.handle_events,
            "/api/venues": self.handle_venues,
            "/api/list": self.handle_list,
            "/api/stats": self.handle_stats,
            "/api/collect": self.handle_collect,
        }

        handler = api_routes.get(path)
        if handler:
            handler(params)
            return

        # Statiska filer
        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        post_routes = {
            "/api/list/add": self.handle_list_add,
            "/api/list/update": self.handle_list_update,
            "/api/list/remove": self.handle_list_remove,
            "/api/artists/follow": self.handle_artist_follow,
        }

        handler = post_routes.get(path)
        if handler:
            handler(body)
        else:
            self.send_json({"error": "Not found"}, 404)

    def serve_static(self, path: str):
        """Servera statisk fil från web/out/."""
        if path == "/":
            path = "/index.html"

        # Prova exakt sökväg, sedan med .html (för Next.js clean URLs)
        candidates = [
            STATIC_DIR / path.lstrip("/"),
            STATIC_DIR / (path.lstrip("/") + ".html"),
            STATIC_DIR / path.lstrip("/") / "index.html",
        ]

        for filepath in candidates:
            if filepath.is_file():
                ext = filepath.suffix
                content_type = MIME_TYPES.get(ext, mimetypes.guess_type(str(filepath))[0] or "application/octet-stream")
                try:
                    data = filepath.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "public, max-age=3600" if ext != ".html" else "no-cache")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except IOError:
                    break

        # 404 — försök visa index.html (SPA fallback)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            data = index.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_json({"error": "Not found"}, 404)

    # --- API handlers ---

    def handle_events(self, params):
        conn = get_connection()
        query = """
            SELECT e.id, e.artist, e.title, e.date, e.time, e.genre, e.subgenre,
                   e.image_url, e.ticket_url, e.ticket_status, e.price_min, e.price_max,
                   e.on_sale_date, e.source,
                   v.name as venue_name, v.city, v.slug as venue_slug, v.venue_type,
                   ul.status as list_status, ul.id as list_id
            FROM events e
            LEFT JOIN venues v ON e.venue_id = v.id
            LEFT JOIN user_lists ul ON ul.event_id = e.id
            WHERE e.date >= date('now')
        """
        query_params: list = []

        if "city" in params:
            query += " AND v.city = ?"
            query_params.append(params["city"][0])

        if "venue" in params:
            query += " AND v.slug = ?"
            query_params.append(params["venue"][0])

        if "genre" in params:
            query += " AND (e.genre LIKE ? OR e.subgenre LIKE ?)"
            g = f"%{params['genre'][0]}%"
            query_params.extend([g, g])

        if "search" in params:
            query += " AND (e.artist LIKE ? OR e.title LIKE ?)"
            s = f"%{params['search'][0]}%"
            query_params.extend([s, s])

        if "from" in params:
            query += " AND e.date >= ?"
            query_params.append(params["from"][0])

        if "to" in params:
            query += " AND e.date <= ?"
            query_params.append(params["to"][0])

        query += " ORDER BY e.date, e.time LIMIT 200"

        rows = conn.execute(query, query_params).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def handle_venues(self, params):
        conn = get_connection()
        city = params.get("city", [None])[0]
        query = "SELECT * FROM venues"
        query_params: list = []
        if city:
            query += " WHERE city = ?"
            query_params.append(city)
        query += " ORDER BY city, name"
        rows = conn.execute(query, query_params).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def handle_list(self, params):
        conn = get_connection()
        rows = conn.execute("""
            SELECT ul.*, e.artist, e.title, e.date, e.time, e.ticket_url,
                   e.ticket_status, e.image_url, e.on_sale_date,
                   v.name as venue_name, v.city
            FROM user_lists ul
            JOIN events e ON ul.event_id = e.id
            LEFT JOIN venues v ON e.venue_id = v.id
            WHERE e.date >= date('now')
            ORDER BY e.date
        """).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def handle_list_add(self, body):
        event_id = body.get("event_id")
        status = body.get("status", "interested")
        if not event_id:
            self.send_json({"error": "event_id krävs"}, 400)
            return
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO user_lists (event_id, status) VALUES (?, ?)",
            (event_id, status),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM user_lists WHERE event_id = ?", (event_id,)
        ).fetchone()
        list_id = row["id"] if row else None
        conn.close()
        self.send_json({"ok": True, "list_id": list_id})

    def handle_list_update(self, body):
        list_id = body.get("list_id")
        conn = get_connection()
        updates = []
        params: list = []
        for field in ["status", "ticket_count", "notes", "remind_before_days"]:
            if field in body:
                updates.append(f"{field} = ?")
                params.append(body[field])
        if updates and list_id:
            params.append(list_id)
            conn.execute(f"UPDATE user_lists SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        conn.close()
        self.send_json({"ok": True})

    def handle_list_remove(self, body):
        list_id = body.get("list_id")
        if list_id:
            conn = get_connection()
            conn.execute("DELETE FROM user_lists WHERE id = ?", (list_id,))
            conn.commit()
            conn.close()
        self.send_json({"ok": True})

    def handle_artist_follow(self, body):
        artist = body.get("artist_name")
        if not artist:
            self.send_json({"error": "artist_name krävs"}, 400)
            return
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO artist_follows (artist_name) VALUES (?)",
            (artist,),
        )
        conn.commit()
        conn.close()
        self.send_json({"ok": True})

    def handle_collect(self, params):
        """Trigga datainsamling. Skyddad med enkel nyckel."""
        key = params.get("key", [None])[0]
        expected = os.environ.get("COLLECT_KEY", "")
        if expected and key != expected:
            self.send_json({"error": "Unauthorized"}, 401)
            return
        import threading
        threading.Thread(target=_run_full_collect, daemon=True).start()
        self.send_json({"ok": True, "message": "Insamling startad i bakgrunden"})

    def handle_stats(self, params):
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) as n FROM events WHERE date >= date('now')").fetchone()["n"]
        by_city = conn.execute("""
            SELECT v.city, COUNT(*) as n FROM events e
            JOIN venues v ON e.venue_id = v.id
            WHERE e.date >= date('now')
            GROUP BY v.city
        """).fetchall()
        by_venue = conn.execute("""
            SELECT v.name, v.city, COUNT(*) as n FROM events e
            JOIN venues v ON e.venue_id = v.id
            WHERE e.date >= date('now')
            GROUP BY v.id ORDER BY n DESC LIMIT 15
        """).fetchall()
        conn.close()
        self.send_json({
            "total_upcoming": total,
            "by_city": [dict(r) for r in by_city],
            "top_venues": [dict(r) for r in by_venue],
        })

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


def main():
    from .db.database import DB_PATH

    init_db()
    seed_venues()

    # Kör insamling i bakgrunden (blockar inte serverstarten)
    def _initial_collect():
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) as n FROM events").fetchone()
        count = row["n"] if isinstance(row, dict) else row[0]
        conn.close()
        if count == 0:
            print("[Init] Tom databas — kör initial datainsamling...")
            _run_full_collect()
        else:
            print(f"[Init] {count} events redan i databasen")
    threading.Thread(target=_initial_collect, daemon=True).start()

    # Starta schemalagd insamling
    _schedule_collect()

    port = int(os.environ.get("PORT", 3001))
    server = HTTPServer(("0.0.0.0", port), APIHandler)
    print(f"Spelningskollen kör på http://0.0.0.0:{port}")
    print(f"  DB: {DB_PATH}")
    if STATIC_DIR.is_dir():
        print(f"  Statiska filer: {STATIC_DIR}")
    else:
        print(f"  OBS: {STATIC_DIR} saknas — kör 'cd web && npm run build' först")
    server.serve_forever()


if __name__ == "__main__":
    main()
