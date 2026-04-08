-- Konsertkalender — databasschema

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,                    -- 'Stockholm' eller 'Uppsala'
    slug TEXT UNIQUE NOT NULL,             -- 'nalen', 'slaktkyrkan', etc.
    address TEXT,
    capacity INTEGER,
    venue_type TEXT DEFAULT 'club',        -- 'arena', 'club', 'outdoor', 'festival'
    website_url TEXT,
    scraper_module TEXT,                   -- 'nalen', 'ticketmaster', etc.
    latitude REAL,
    longitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,                      -- ID från källsystem
    source TEXT NOT NULL,                  -- 'ticketmaster', 'songkick', 'scraper:nalen'
    venue_id INTEGER REFERENCES venues(id),
    artist TEXT NOT NULL,
    title TEXT,                            -- Eventnamn (kan skilja från artist)
    date DATE NOT NULL,
    time TIME,
    doors_open TIME,
    genre TEXT,
    subgenre TEXT,
    description TEXT,
    image_url TEXT,
    ticket_url TEXT,
    ticket_status TEXT DEFAULT 'unknown',  -- 'on_sale', 'sold_out', 'presale', 'announced', 'unknown'
    price_min REAL,
    price_max REAL,
    currency TEXT DEFAULT 'SEK',
    on_sale_date TIMESTAMP,               -- När biljetter släpps
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)           -- Undvik dubbletter per källa
);

CREATE TABLE IF NOT EXISTS user_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'interested',      -- 'interested', 'going', 'bought_ticket'
    ticket_count INTEGER DEFAULT 0,
    notes TEXT,
    remind_before_days INTEGER DEFAULT 1,  -- Påminn X dagar innan
    remind_ticket_release BOOLEAN DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL UNIQUE,       -- Normaliserat artistnamn
    notify_new_events BOOLEAN DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_list_id INTEGER REFERENCES user_lists(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    reminder_type TEXT NOT NULL,            -- 'before_event', 'ticket_release', 'new_event_artist'
    remind_at TIMESTAMP NOT NULL,
    sent BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS venue_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(id),
    alias TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_venue_aliases_alias ON venue_aliases(alias);

CREATE TABLE IF NOT EXISTS event_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_event_id INTEGER NOT NULL REFERENCES events(id),
    matched_event_id INTEGER NOT NULL REFERENCES events(id),
    confidence REAL NOT NULL,
    match_method TEXT NOT NULL,              -- 'exact', 'fuzzy_artist', 'manual'
    verified BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(canonical_event_id, matched_event_id)
);

CREATE TABLE IF NOT EXISTS genre_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_genre TEXT NOT NULL UNIQUE,
    normalized TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collect_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    events_found INTEGER DEFAULT 0,
    events_new INTEGER DEFAULT 0,
    errors TEXT,
    duration_ms INTEGER,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collect_log_source ON collect_log(source, collected_at);

-- Index för vanliga queries
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_artist ON events(artist);
CREATE INDEX IF NOT EXISTS idx_events_venue ON events(venue_id);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source, external_id);
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders(sent, remind_at);
CREATE INDEX IF NOT EXISTS idx_event_changes_event ON event_changes(event_id);
CREATE INDEX IF NOT EXISTS idx_event_matches_canonical ON event_matches(canonical_event_id);
CREATE INDEX IF NOT EXISTS idx_event_matches_matched ON event_matches(matched_event_id);

-- ── Personalisering ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1 UNIQUE,
    onboarding_done BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_genre_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    genre TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 0.5,
    UNIQUE(user_id, genre)
);

CREATE TABLE IF NOT EXISTS user_venue_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    venue_id INTEGER NOT NULL REFERENCES venues(id),
    weight REAL NOT NULL DEFAULT 0.5,
    UNIQUE(user_id, venue_id)
);

CREATE TABLE IF NOT EXISTS user_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    event_id INTEGER NOT NULL REFERENCES events(id),
    interaction_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artist_enrichment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL UNIQUE,
    spotify_id TEXT,
    genres TEXT,
    popularity INTEGER,
    related_artists TEXT,
    image_url TEXT,
    source TEXT DEFAULT 'spotify',
    enriched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL DEFAULT 1,
    score REAL NOT NULL DEFAULT 0.0,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_event_scores_user ON event_scores(user_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_user_interactions_user ON user_interactions(user_id, event_id);
CREATE INDEX IF NOT EXISTS idx_artist_enrichment_name ON artist_enrichment(artist_name);
