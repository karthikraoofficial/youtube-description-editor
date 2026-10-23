CREATE TABLE channel (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    avatar_url TEXT,
    uploads_playlist_id TEXT NOT NULL,
    connected_at TEXT NOT NULL
);
