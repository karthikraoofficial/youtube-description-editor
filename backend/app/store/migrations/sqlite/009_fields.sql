-- The Field a Changeset edits, and the Field each Run writes (ADR-0022). Rows from before Fields existed edited
-- the description. A Run carries its own Field so a Restore of a Restore needs no chain of lookups.
ALTER TABLE changesets ADD COLUMN field TEXT NOT NULL DEFAULT 'description';
ALTER TABLE runs ADD COLUMN field TEXT NOT NULL DEFAULT 'description';
