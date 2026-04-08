"""Claude-baserad genre-klassificering för okända artister.

Fallback när Spotify inte hittar artisten.
Kräver ANTHROPIC_API_KEY i .env. Max 50 per körning.
"""
from __future__ import annotations

import os
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"

KNOWN_GENRES = [
    "rock", "pop", "elektroniskt", "jazz", "hiphop",
    "klassiskt", "metal", "singer-songwriter", "världsmusik", "övrigt",
]


def classify_artist(artist_name: str, venue: str = "", title: str = "") -> dict | None:
    """
    Klassificera en artist med Claude.
    Returnerar dict med 'genres', 'popularity_estimate', 'source' = 'claude'.
    """
    if not ANTHROPIC_API_KEY:
        return None

    context = f"Artist: {artist_name}"
    if venue:
        context += f"\nVenue: {venue}"
    if title:
        context += f"\nEvent-titel: {title}"

    prompt = f"""{context}

Svara ENBART med ett JSON-objekt, inget annat:
{{
  "genres": ["<en eller två av: rock, pop, elektroniskt, jazz, hiphop, klassiskt, metal, singer-songwriter, världsmusik, övrigt>"],
  "popularity_estimate": <0-100 uppskattad popularitet baserat på kändisgrad>,
  "related_artists": ["<0-3 liknande artister om du vet>"]
}}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"].strip()
        # Extrahera JSON (Claude kan ibland wrappa i ```json```)
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except Exception:
        return None

    genres = [g for g in data.get("genres", []) if g in KNOWN_GENRES]
    if not genres:
        genres = ["övrigt"]

    return {
        "artist_name": artist_name,
        "spotify_id": None,
        "genres": json.dumps(genres),
        "popularity": data.get("popularity_estimate"),
        "related_artists": json.dumps(data.get("related_artists", [])),
        "image_url": None,
        "source": "claude",
    }
