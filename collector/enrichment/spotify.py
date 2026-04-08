"""Spotify Artist Enrichment för Spelningskollen.

Hämtar genres, popularity, related artists och bild för artister.
Kräver SPOTIFY_CLIENT_ID och SPOTIFY_CLIENT_SECRET i .env.
"""
from __future__ import annotations

import os
import json
import time
import base64
import requests

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
_token_cache: dict = {}


def _get_token() -> str | None:
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    now = time.time()
    if _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["token"]

    creds = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {creds}"},
        timeout=10,
    )
    if not resp.ok:
        return None
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["token"]


def enrich_artist(artist_name: str) -> dict | None:
    """
    Sök upp en artist på Spotify och returnera enrichment-data.
    Returnerar dict eller None om ej hittad.
    """
    token = _get_token()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    # Sök artist
    resp = requests.get(
        "https://api.spotify.com/v1/search",
        params={"q": artist_name, "type": "artist", "limit": 1, "market": "SE"},
        headers=headers,
        timeout=10,
    )
    time.sleep(0.1)  # Respektera rate limit
    if not resp.ok:
        return None

    items = resp.json().get("artists", {}).get("items", [])
    if not items:
        return None

    artist = items[0]
    # Kontrollera att vi fick rätt artist (namnmatch)
    if artist["name"].lower() != artist_name.lower():
        # Acceptera om namnlikheten är hög nog
        from ..matching import normalize_artist
        if normalize_artist(artist["name"]) != normalize_artist(artist_name):
            return None

    spotify_id = artist["id"]

    # Hämta related artists
    related_resp = requests.get(
        f"https://api.spotify.com/v1/artists/{spotify_id}/related-artists",
        headers=headers,
        timeout=10,
    )
    time.sleep(0.1)
    related = []
    if related_resp.ok:
        related = [a["name"] for a in related_resp.json().get("artists", [])[:10]]

    # Bild
    images = artist.get("images", [])
    image_url = images[0]["url"] if images else None

    return {
        "artist_name": artist_name,
        "spotify_id": spotify_id,
        "genres": json.dumps(artist.get("genres", [])),
        "popularity": artist.get("popularity"),
        "related_artists": json.dumps(related),
        "image_url": image_url,
        "source": "spotify",
    }
