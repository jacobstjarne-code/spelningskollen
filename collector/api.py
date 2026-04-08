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
import time
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from .db.database import get_connection, init_db, seed_venues

# Rate limiting
_REQUEST_LOG: dict = defaultdict(list)
_RATE_LIMIT = int(os.environ.get("RATE_LIMIT", 60))  # requests/minut/IP
_RATE_LOCK = threading.Lock()


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        _REQUEST_LOG[ip] = [t for t in _REQUEST_LOG[ip] if now - t < 60]
        if len(_REQUEST_LOG[ip]) >= _RATE_LIMIT:
            return True
        _REQUEST_LOG[ip].append(now)
    return False

STATIC_DIR = Path(__file__).parent.parent / "web" / "out"

# Insamlingsintervall (sekunder). Default: var 6:e timme.
COLLECT_INTERVAL = int(os.environ.get("COLLECT_INTERVAL", 6 * 3600))


def _log_collect(source: str, events_found: int, errors: str | None, duration_ms: int):
    """Logga en insamlingskörning till collect_log."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO collect_log (source, events_found, errors, duration_ms)
               VALUES (?, ?, ?, ?)""",
            (source, events_found, errors, duration_ms)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _run_full_collect():
    """Kör alla datakällor. Scraper-listan importeras från main.py för att undvika avvikelser."""
    import time
    from .sources import ticketmaster
    from .sources import bandsintown, resident_advisor
    from .main import ALL_SCRAPERS
    from .matching import post_collect_match
    from .db.database import get_connection

    total = 0

    # API-källor
    for label, fn in [
        ("ticketmaster", ticketmaster.collect),
        ("bandsintown", bandsintown.collect),
        ("resident_advisor", resident_advisor.collect),
    ]:
        t0 = int(time.time() * 1000)
        err = None
        n = 0
        try:
            n = fn()
            print(f"[Collect] {label}: {n} events")
            total += n
        except Exception as e:
            err = str(e)
            print(f"[Collect] {label}: FEL — {e}")
        _log_collect(label, n, err, int(time.time() * 1000) - t0)

    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        label = scraper_cls.__name__.replace("Scraper", "").lower()
        t0 = int(time.time() * 1000)
        err = None
        n = 0
        try:
            n = scraper.collect()
            print(f"[Collect] {scraper_cls.__name__}: {n} events")
            total += n
        except Exception as e:
            err = str(e)
            print(f"[Collect] {scraper_cls.__name__}: FEL — {e}")
        _log_collect(label, n, err, int(time.time() * 1000) - t0)

    # Ladda ner bilder för nya events
    try:
        from .images import process_pending_images
        downloaded = process_pending_images(limit=50)
        if downloaded:
            print(f"[Bilder] {downloaded} nya bilder nedladdade")
    except Exception as e:
        print(f"[Bilder] FEL — {e}")

    # Kör matchning på alla events som samlats in senaste timmen
    try:
        conn = get_connection()
        recent = conn.execute(
            """SELECT id FROM events
               WHERE last_updated >= datetime('now', '-1 hour')
               AND canonical_id IS NULL"""
        ).fetchall()
        conn.close()
        recent_ids = [r["id"] for r in recent]
        if recent_ids:
            merged, cands = post_collect_match(recent_ids)
            print(f"[Matching] {merged} auto-mergade, {cands} kandidater sparade")
    except Exception as e:
        print(f"[Matching] FEL — {e}")

    # Artist-bevakning
    try:
        from .artist_monitor import check_new_events_for_followed_artists
        n = check_new_events_for_followed_artists()
        if n:
            print(f"[Artists] {n} nya reminders för bevakade artister")
    except Exception as e:
        print(f"[Artists] FEL — {e}")

    # Enrichment: Spotify + Claude genre-klassificering
    try:
        from .enrichment.pipeline import enrich_pending_artists, backfill_event_genres
        enriched = enrich_pending_artists(max_artists=50)
        if enriched:
            print(f"[Enrichment] {enriched} artister berikade")
        filled = backfill_event_genres()
        if filled:
            print(f"[Enrichment] {filled} events fick genre från enrichment")
    except Exception as e:
        print(f"[Enrichment] FEL — {e}")

    print(f"[Collect] Klart: {total} events totalt")
    return total


def _schedule_collect():
    """Kör insamling och biljettsbevakning i bakgrunden."""
    def loop():
        import time
        tick_counter = 0
        PUSH_INTERVAL = max(1, 900 // COLLECT_INTERVAL) if COLLECT_INTERVAL > 0 else 1  # ~15 min
        while True:
            time.sleep(COLLECT_INTERVAL)
            tick_counter += 1
            print(f"[Cron] Startar schemalagd insamling...")
            try:
                _run_full_collect()
            except Exception as e:
                print(f"[Cron] Insamling fel: {e}")
            # Biljettsläpp-bevakning var 2:a körning
            if tick_counter % 2 == 0:
                try:
                    from .ticket_watcher import check_ticket_updates
                    n = check_ticket_updates()
                    if n:
                        print(f"[Tickets] {n} events uppdaterade")
                except Exception as e:
                    print(f"[Tickets] Fel: {e}")
            # Push-notiser var PUSH_INTERVAL körning
            try:
                from .push import check_and_send_reminders
                n = check_and_send_reminders()
                if n:
                    print(f"[Push] {n} notiser skickade")
            except Exception as e:
                print(f"[Push] Fel: {e}")
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

        # Rate limiting (bara på API-routes)
        if path.startswith("/api/"):
            ip = self.client_address[0]
            if _is_rate_limited(ip):
                self.send_json({"error": "Too Many Requests"}, 429)
                return

        # API-routes
        api_routes = {
            "/api/events": self.handle_events,
            "/api/venues": self.handle_venues,
            "/api/list": self.handle_list,
            "/api/stats": self.handle_stats,
            "/api/collect": self.handle_collect,
            "/api/admin/match-candidates": self.handle_match_candidates,
            "/api/admin/collect-log": self.handle_collect_log,
            "/api/list/share": self.handle_list_share_get,
            "/api/profile": self.handle_profile_get,
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
            "/api/admin/match-verify": self.handle_match_verify,
            "/api/list/share/generate": self.handle_list_share_generate,
            "/api/push/subscribe": self.handle_push_subscribe,
            "/api/push/unsubscribe": self.handle_push_unsubscribe,
            "/api/profile/onboarding": self.handle_onboarding,
            "/api/profile/genres": self.handle_profile_genres,
            "/api/profile/venues": self.handle_profile_venues,
            "/api/interactions": self.handle_interaction,
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
        personalized = params.get("personalized", [""])[0] == "true"

        score_join = "LEFT JOIN event_scores es_p ON es_p.event_id = e.id AND es_p.user_id = 1" if personalized else ""
        score_select = ", COALESCE(es_p.score, 0) as score" if personalized else ", NULL as score"
        order = "ORDER BY COALESCE(es_p.score, 0) DESC, e.date" if personalized else "ORDER BY e.date, e.time"

        query = f"""
            SELECT e.id, e.artist, e.title, e.date, e.time, e.genre, e.subgenre,
                   e.image_url, e.ticket_url, e.ticket_status, e.price_min, e.price_max,
                   e.on_sale_date, e.source,
                   v.name as venue_name, v.city, v.slug as venue_slug, v.venue_type,
                   ul.status as list_status, ul.id as list_id,
                   pc.price_prev {score_select}
            FROM events e
            LEFT JOIN venues v ON e.venue_id = v.id
            LEFT JOIN user_lists ul ON ul.event_id = e.id
            LEFT JOIN (
                SELECT event_id, CAST(old_value AS REAL) as price_prev
                FROM event_changes
                WHERE field = 'price_min'
                GROUP BY event_id
                HAVING detected_at = MAX(detected_at)
            ) pc ON pc.event_id = e.id
            {score_join}
            WHERE e.date >= date('now')
              AND e.canonical_id IS NULL
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

        query += f" {order} LIMIT 200"

        rows = conn.execute(query, query_params).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows], cache_seconds=0 if personalized else 300)

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

    ALLOWED_LIST_FIELDS = {'status', 'ticket_count', 'notes', 'remind_before_days'}

    def handle_list_update(self, body):
        list_id = body.get("list_id")
        conn = get_connection()
        updates = []
        params: list = []
        for field in self.ALLOWED_LIST_FIELDS:
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

    def handle_list_share_get(self, params):
        """Hämta delad lista via share_token."""
        token = params.get("token", [None])[0]
        if not token:
            self.send_json({"error": "token krävs"}, 400)
            return
        conn = get_connection()
        rows = conn.execute("""
            SELECT ul.status, e.artist, e.title, e.date, e.time,
                   e.ticket_url, e.ticket_status, e.image_url,
                   v.name as venue_name, v.city
            FROM user_lists ul
            JOIN events e ON ul.event_id = e.id
            LEFT JOIN venues v ON e.venue_id = v.id
            WHERE ul.share_token = ? AND e.date >= date('now')
            ORDER BY e.date
        """, (token,)).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def handle_list_share_generate(self, body):
        """Generera share_token för user_list-rad."""
        list_id = body.get("list_id")
        if not list_id:
            self.send_json({"error": "list_id krävs"}, 400)
            return
        import secrets
        token = secrets.token_urlsafe(12)
        conn = get_connection()
        conn.execute(
            "UPDATE user_lists SET share_token = ? WHERE id = ?",
            (token, list_id)
        )
        conn.commit()
        conn.close()
        self.send_json({"ok": True, "token": token})

    def handle_collect_log(self, params):
        """Senaste insamlingskörning per källa."""
        key = params.get("key", [None])[0]
        expected = os.environ.get("COLLECT_KEY", "")
        if expected and key != expected:
            self.send_json({"error": "Unauthorized"}, 401)
            return
        conn = get_connection()
        rows = conn.execute("""
            SELECT source,
                   MAX(collected_at) as last_run,
                   SUM(events_found) as total_events,
                   MAX(events_found) as last_count,
                   SUM(CASE WHEN errors IS NOT NULL THEN 1 ELSE 0 END) as error_count,
                   MAX(errors) as last_error,
                   AVG(duration_ms) as avg_duration_ms
            FROM collect_log
            WHERE collected_at >= datetime('now', '-7 days')
            GROUP BY source
            ORDER BY last_run DESC
        """).fetchall()
        conn.close()
        self.send_json([dict(r) for r in rows])

    def handle_push_subscribe(self, body):
        endpoint = body.get("endpoint")
        keys = body.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")
        if not all([endpoint, p256dh, auth]):
            self.send_json({"error": "endpoint och keys.p256dh/auth krävs"}, 400)
            return
        from .push import subscribe
        ok = subscribe(endpoint, p256dh, auth)
        self.send_json({"ok": ok})

    def handle_push_unsubscribe(self, body):
        endpoint = body.get("endpoint")
        if not endpoint:
            self.send_json({"error": "endpoint krävs"}, 400)
            return
        from .push import unsubscribe
        unsubscribe(endpoint)
        self.send_json({"ok": True})

    def handle_match_candidates(self, params):
        """Returnerar ej verifierade matchkandidater för manuell granskning."""
        key = params.get("key", [None])[0]
        expected = os.environ.get("COLLECT_KEY", "")
        if expected and key != expected:
            self.send_json({"error": "Unauthorized"}, 401)
            return
        conn = get_connection()
        rows = conn.execute("""
            SELECT em.id as match_id, em.confidence, em.match_method,
                   ce.id as canonical_id, ce.artist as canonical_artist,
                   ce.date as canonical_date, ce.source as canonical_source,
                   cv.name as canonical_venue,
                   me.id as candidate_id, me.artist as candidate_artist,
                   me.date as candidate_date, me.source as candidate_source,
                   mv.name as candidate_venue
            FROM event_matches em
            JOIN events ce ON em.canonical_event_id = ce.id
            LEFT JOIN venues cv ON ce.venue_id = cv.id
            JOIN events me ON em.matched_event_id = me.id
            LEFT JOIN venues mv ON me.venue_id = mv.id
            WHERE em.verified = 0
            ORDER BY em.confidence DESC
            LIMIT 100
        """).fetchall()
        conn.close()
        result = []
        for r in rows:
            r = dict(r)
            result.append({
                "match_id": r["match_id"],
                "confidence": r["confidence"],
                "match_method": r["match_method"],
                "canonical": {
                    "id": r["canonical_id"],
                    "artist": r["canonical_artist"],
                    "date": r["canonical_date"],
                    "venue": r["canonical_venue"],
                    "source": r["canonical_source"],
                },
                "candidate": {
                    "id": r["candidate_id"],
                    "artist": r["candidate_artist"],
                    "date": r["candidate_date"],
                    "venue": r["candidate_venue"],
                    "source": r["candidate_source"],
                },
            })
        self.send_json(result)

    def handle_match_verify(self, body):
        """Verifiera eller avvisa en matchkandid."""
        match_id = body.get("match_id")
        action = body.get("action")  # 'merge' eller 'reject'
        key = body.get("key", "")
        expected = os.environ.get("COLLECT_KEY", "")
        if expected and key != expected:
            self.send_json({"error": "Unauthorized"}, 401)
            return
        if not match_id or action not in ("merge", "reject"):
            self.send_json({"error": "match_id och action (merge/reject) krävs"}, 400)
            return
        conn = get_connection()
        row = conn.execute(
            "SELECT canonical_event_id, matched_event_id FROM event_matches WHERE id = ?",
            (match_id,)
        ).fetchone()
        conn.close()
        if not row:
            self.send_json({"error": "Match ej hittad"}, 404)
            return
        if action == "merge":
            from .matching import merge_events
            merge_events(row["canonical_event_id"], row["matched_event_id"])
        conn = get_connection()
        conn.execute("UPDATE event_matches SET verified = 1 WHERE id = ?", (match_id,))
        conn.commit()
        conn.close()
        self.send_json({"ok": True, "action": action})

    def handle_profile_get(self, params):
        """GET /api/profile — returnerar profil-snapshot."""
        from .profile_engine import get_profile
        self.send_json(get_profile(1))

    def handle_onboarding(self, body):
        """POST /api/profile/onboarding — spara onboarding-val, starta score-beräkning."""
        from .profile_engine import save_onboarding
        genres = body.get("genres", [])
        venues = body.get("venues", [])
        artists = body.get("artists", [])
        if not isinstance(genres, list) or not isinstance(venues, list):
            self.send_json({"error": "genres och venues måste vara listor"}, 400)
            return
        save_onboarding(1, genres, venues, artists)
        # Starta score-beräkning i bakgrunden
        import threading
        from .recommender import compute_scores_for_user
        threading.Thread(target=compute_scores_for_user, args=(1,), daemon=True).start()
        self.send_json({"ok": True})

    def handle_profile_genres(self, body):
        """PUT /api/profile/genres — uppdatera genrevikter."""
        from .db.database import get_connection
        genres = body.get("genres", {})
        if not isinstance(genres, dict):
            self.send_json({"error": "genres måste vara ett objekt {genre: weight}"}, 400)
            return
        conn = get_connection()
        for genre, weight in genres.items():
            try:
                w = float(weight)
                w = max(0.0, min(1.0, w))
                conn.execute(
                    """INSERT OR REPLACE INTO user_genre_preferences (user_id, genre, weight)
                       VALUES (1, ?, ?)""",
                    (genre, w),
                )
            except (ValueError, TypeError):
                pass
        conn.commit()
        conn.close()
        self.send_json({"ok": True})

    def handle_profile_venues(self, body):
        """PUT /api/profile/venues — uppdatera venue-preferenser via slug."""
        from .db.database import get_connection
        venues = body.get("venues", {})
        if not isinstance(venues, dict):
            self.send_json({"error": "venues måste vara {slug: weight}"}, 400)
            return
        conn = get_connection()
        for slug, weight in venues.items():
            try:
                row = conn.execute("SELECT id FROM venues WHERE slug = ?", (slug,)).fetchone()
                if row:
                    w = max(0.0, min(1.0, float(weight)))
                    conn.execute(
                        """INSERT OR REPLACE INTO user_venue_preferences (user_id, venue_id, weight)
                           VALUES (1, ?, ?)""",
                        (row["id"], w),
                    )
            except (ValueError, TypeError):
                pass
        conn.commit()
        conn.close()
        self.send_json({"ok": True})

    def handle_interaction(self, body):
        """POST /api/interactions — spara interaktion och uppdatera vikter."""
        from .profile_engine import record_interaction
        event_id = body.get("event_id")
        interaction_type = body.get("type")
        VALID_TYPES = {"click", "save", "buy", "unsave", "dismiss"}
        if not event_id or interaction_type not in VALID_TYPES:
            self.send_json({"error": "event_id och type (click/save/buy/unsave/dismiss) krävs"}, 400)
            return
        try:
            record_interaction(1, int(event_id), interaction_type)
            self.send_json({"ok": True})
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def send_json(self, data, status=200, cache_seconds=0):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if cache_seconds > 0:
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        else:
            self.send_header("Cache-Control", "no-cache")
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
