-- A Pause or Cancel the owner asked for while the Run was writing; the engine acts on it between Videos.
ALTER TABLE runs ADD COLUMN control TEXT CHECK (control IN ('pause', 'cancel'));
