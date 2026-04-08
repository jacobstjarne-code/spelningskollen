"""Genre-normalisering för Spelningskollen.

Mappar rågenre-strängar (från scrapers och Ticketmaster) till 10 normaliserade kategorier.
"""
from __future__ import annotations

GENRE_KEYWORDS: dict[str, list[str]] = {
    "rock": ["rock", "alternative", "indie", "punk", "garage", "grunge", "post-rock", "shoegaze"],
    "elektroniskt": ["electronic", "edm", "techno", "house", "dj", "dance", "trance",
                     "drum and bass", "dubstep", "ambient", "synth", "electronica"],
    "jazz": ["jazz", "soul", "funk", "blues", "bebop", "swing", "big band"],
    "hiphop": ["hip-hop", "hip hop", "rap", "r&b", "rnb", "trap", "grime"],
    "singer-songwriter": ["singer", "songwriter", "folk", "acoustic", "americana", "country"],
    "klassiskt": ["classical", "opera", "chamber", "orchestral", "symphony", "philharmonic",
                  "klassisk", "kammar", "orkester"],
    "metal": ["metal", "heavy metal", "death metal", "hardcore", "doom", "black metal",
              "thrash", "stoner", "sludge"],
    "pop": ["pop", "schlager", "dansband"],
    "världsmusik": ["world", "latin", "reggae", "afrobeat", "cumbia", "fado", "klezmer",
                    "salsa", "flamenco", "bossa", "samba", "afropop", "afro"],
}


def normalize_genre(raw: str | None) -> str:
    """Returnerar normaliserad genre (en av 10 kategorier + 'övrigt')."""
    if not raw:
        return "övrigt"
    lower = raw.lower()
    for normalized, keywords in GENRE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return normalized
    return "övrigt"
