CREATE TABLE runs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('apply', 'restore')),
    changeset_id INTEGER REFERENCES changesets (id),
    source_run_id INTEGER REFERENCES runs (id),
    status TEXT NOT NULL CHECK (status IN
        ('pending', 'running', 'paused', 'paused_quota', 'interrupted', 'cancelled', 'completed')),
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE run_items (
    run_id INTEGER NOT NULL REFERENCES runs (id),
    video_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    title TEXT NOT NULL,
    expected_before TEXT NOT NULL,     -- the description the owner reviewed
    target_description TEXT NOT NULL,
    backup_snippet_json TEXT,          -- the live snippet, saved before the Run's first write
    status TEXT NOT NULL CHECK (status IN
        ('pending', 'success', 'failed', 'stale', 'blocked', 'noop', 'cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, video_id)
);

CREATE TABLE run_log (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs (id),
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
