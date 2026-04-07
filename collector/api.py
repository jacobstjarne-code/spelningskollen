"""Enkelt JSON API för konsertkalendern.

Körs som: python -m collector.api
Serverar events från SQLite som JSON.
Används av Next.js frontend under utveckling.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import date, datetime
from .db.database import get_connection, init_db, seed_venues


class APIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        routes = {
            "/api/events": self.handle_events,
            "/api/venues": self.handle_venues,
            "/api/list": self.handle_list,
            "/api/stats": self.handle_stats,
        }

        handler = routes.get(path)
        if handler:
            handler(params)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if path == "/api/list/add":
            self.handle_list_add(body)
        elif path == "/api/list/update":
            self.handle_list_update(body)
        elif path == "/api/list/remove":
            self.handle_list_remove(body)
        elif path == "/api/artists/follow":
            self.handle_artist_follow(body)
        else:
            self.send_json({"error": "Not found"}, 404)

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
        query_params = []

        # Filtrering
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
        query_params = []
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
                   e.ticket_status, e.image_url,
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
        conn.close()
        self.send_json({"ok": True})

    def handle_list_update(self, body):
        list_id = body.get("list_id")
        conn = get_connection()
        updates = []
        params = []
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
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

    def do_OPTIONS(self):
        self.send_json({})

    def log_message(self, format, *args):
        print(f"[API] {args[0]}")


def main():
    init_db()
    seed_venues()
    port = 3001
    server = HTTPServer(("localhost", port), APIHandler)
    print(f"Konsertkalender API kör på http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
