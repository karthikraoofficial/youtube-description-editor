# The Backup copy goes to an archive: local files, or a private Vercel Blob store

Every Run saves its Backups twice before its first write: once in the database, and once as a JSON copy. Locally the copy has always been `data/backups/run-<id>.json`. A serverless function has no lasting disk, so in the cloud the copy goes to a **private** Vercel Blob store instead, at `backups/run-<id>.json`. Reading a private store needs the store's credentials, so the copy is no easier to reach than the database. The app turns this on when the environment has a Blob credential: `BLOB_READ_WRITE_TOKEN`, or Vercel's OIDC token with `BLOB_STORE_ID`. Uploads use Vercel's own Python SDK (`vercel-blob`).

**The database is the source; the copy is rebuilt from it.** Each Step saves first-time Backups in the database, keeping the first one per Video, then writes the whole document again from those rows, overwriting the earlier copy. The copy never has to be read back. A copy that failed to save once is complete the next time. Both copies keep the first Backup of each Video in the Run.

**No copy, no write.** If the copy can't be saved, the Step stops the Run as paused before any write, with the Videos still queued, and logs why. The hard rule is a backup before the first write, and a second copy that silently went missing would make that rule weaker without anyone noticing.

The ticket first asked for a random suffix on each blob's path, so a public URL couldn't be guessed. A private store makes that unnecessary, and a fixed path lets each Step overwrite the copy instead of piling up versions.
