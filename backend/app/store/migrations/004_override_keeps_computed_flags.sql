-- The Operation's own verdict, kept so a hand edit (Override) can be reset to it. Some verdicts, such as
-- broken markers, can't be recomputed from text alone.
ALTER TABLE changeset_items ADD COLUMN computed_flags_json TEXT;
UPDATE changeset_items SET computed_flags_json = flags_json;
