"""Bildhantering för Spelningskollen.

Laddar ner och komprimerar event-bilder till lokal katalog.
Används vid deployment på Render free tier där externa CDN-bilder
kan blockeras eller försvinna.
"""
from __future__ import annotations

import os
import requests
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from .db.database import get_connection

IMAGE_DIR = Path(__file__).parent.parent / "web" / "public" / "images" / "events"
THUMB_SIZE = (400, 400)


def download_and_resize(event_id: int, image_url: str) -> str | None:
    """
    Ladda ner och komprimera en event-bild.
    Returnerar relativ sökväg (/images/events/{id}.jpg) eller None vid fel.
    """
    if not image_url or not _PIL_AVAILABLE:
        return None

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{event_id}.jpg"
    filepath = IMAGE_DIR / filename

    if filepath.exists():
        return f"/images/events/{filename}"

    try:
        resp = requests.get(image_url, timeout=10, headers={
            "User-Agent": "Spelningskollen/1.0"
        })
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        img.thumbnail(THUMB_SIZE)
        img = img.convert("RGB")
        img.save(filepath, "JPEG", quality=80, optimize=True)
        return f"/images/events/{filename}"
    except Exception as e:
        print(f"  Bild {event_id}: {e}")
        return None


def process_pending_images(limit: int = 50) -> int:
    """
    Ladda ner bilder för events som saknar lokal kopia.
    Körs efter insamling. Returnerar antal nedladdade bilder.
    """
    if not _PIL_AVAILABLE:
        print("  [Bilder] Pillow ej installerat — hoppar bildhantering")
        return 0

    conn = get_connection()
    events = conn.execute("""
        SELECT id, image_url FROM events
        WHERE image_url IS NOT NULL
          AND local_image_path IS NULL
          AND date >= date('now')
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()

    downloaded = 0
    for e in events:
        path = download_and_resize(e["id"], e["image_url"])
        if path:
            conn2 = get_connection()
            conn2.execute(
                "UPDATE events SET local_image_path = ? WHERE id = ?",
                (path, e["id"])
            )
            conn2.commit()
            conn2.close()
            downloaded += 1

    return downloaded
