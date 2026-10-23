-- Named claims on one-at-a-time work across every instance of the app, such as Sync (ADR-0020). Only the
-- holder may release its claim; anyone may take it over once it has run out.
CREATE TABLE leases (
    name TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    until_s BIGINT NOT NULL  -- epoch seconds
);
