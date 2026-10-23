# Local-only app in a public repo

_Local mode only. A deployment (cloud mode) is protected by the Owner's sign-in and session instead (ADR-0019), and takes its Host and CORS origin from `YDE_PUBLIC_URL` (ADR-0020)._

In local mode the app runs only on the owner's machine:
- The API binds to 127.0.0.1.
- CORS allows only the Vite origin.
- Mutating requests need a custom header, so other web pages open in the browser cannot drive the API.
- Requests whose `Host` is not `127.0.0.1` or `localhost` are rejected, which defeats DNS-rebinding pages.

Because the source is public, all secrets and personal data (`client_secret.json`, `app.db`, which since ADR-0019 also holds the Google sign-in, and backups) live under a gitignored `data/` folder. A pre-commit hook blocks those files and anything that looks like a Google credential, and logs go through a redacting filter. The filter also covers tracebacks and uvicorn's own loggers, which don't propagate to the root logger.
