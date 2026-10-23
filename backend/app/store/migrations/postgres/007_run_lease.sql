-- Which browser tab is driving a Run in Steps, and until when (epoch seconds) it holds the lease (ADR-0017).
ALTER TABLE runs ADD COLUMN driver TEXT;
ALTER TABLE runs ADD COLUMN lease_until BIGINT;
-- Set while a Step is writing the Run, so a second Step (a duplicated tab, say) can't write it at the same time,
-- and a Step that outlived its lease can't change the Run afterwards.
ALTER TABLE runs ADD COLUMN step_token TEXT;
