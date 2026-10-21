CREATE TABLE videos (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category_id TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    default_language TEXT,
    default_audio_language TEXT,
    published_at TEXT NOT NULL,
    duration_s INTEGER NOT NULL,
    privacy_status TEXT NOT NULL,
    thumbnail_url TEXT,
    is_short INTEGER,           -- NULL until classified
    short_source TEXT,          -- probe | duration | manual
    synced_at TEXT NOT NULL,
    last_edited_run_id INTEGER
);
CREATE INDEX videos_published_at ON videos (published_at DESC);

CREATE TABLE quota_events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    pt_date TEXT NOT NULL,
    method TEXT NOT NULL,
    units INTEGER NOT NULL,
    run_id INTEGER
);
CREATE INDEX quota_events_pt_date ON quota_events (pt_date);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
