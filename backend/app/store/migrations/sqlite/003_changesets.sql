CREATE TABLE changesets (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    operation_json TEXT NOT NULL,
    requested INTEGER NOT NULL,     -- how many Video ids the owner selected
    status TEXT NOT NULL CHECK (status IN ('draft', 'discarded', 'applied'))
);

CREATE TABLE changeset_items (
    changeset_id INTEGER NOT NULL REFERENCES changesets (id),
    video_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    title TEXT NOT NULL,
    before_description TEXT NOT NULL,
    computed_description TEXT NOT NULL,
    override_description TEXT,      -- hand edit, if any
    changed INTEGER NOT NULL,
    included INTEGER NOT NULL,
    flags_json TEXT NOT NULL,
    PRIMARY KEY (changeset_id, video_id)
);
