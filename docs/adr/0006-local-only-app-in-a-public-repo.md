# Local-only app in a public repo

The app runs only on the owner's machine:
- The API binds to 127.0.0.1.
- CORS allows only the Vite origin.
- Mutating requests need a custom header, so other web pages open in the browser cannot drive the API.

Because the source is public, all secrets and personal data (`client_secret.json`, `token.json`, `app.db`, backups) live under a gitignored `data/` folder. A pre-commit hook blocks those files and anything that looks like a Google credential, and logs go through a redacting filter.
