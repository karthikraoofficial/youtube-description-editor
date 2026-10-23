# One Google sign-in proves the Owner and connects the Channel

_For cloud mode this supersedes ADR-0006's localhost-only protections; ADR-0006 still governs local mode._

The deployed app must let in exactly one person: the Owner. The app already needs the Owner's Google sign-in to reach YouTube. So that same sign-in, through Google's **web** OAuth flow, also proves who they are:
1. `GET /api/auth/login` sends the browser to Google, asking for `openid email` plus `youtube.force-ssl` in one consent. A random `state` goes into a short-lived HttpOnly cookie.
2. Google sends the browser back to `GET /api/auth/callback`. The callback checks the `state` against the cookie, trades the code for credentials, and reads the email from Google's signed ID token.
3. Only a **verified** email equal to `YDE_OWNER_EMAIL` (ignoring case) is accepted.
   - **Brand Accounts:** when the Channel belongs to a YouTube Brand Account, Google signs the Owner in as that account's Google-issued identity, `…@pages.plusgoogle.com`, which may not carry `email_verified`. Only Google issues addresses in that domain, and they arrive in Google's signed ID token, so the app accepts them unverified. `YDE_OWNER_EMAIL` is then that address.
   - **Any other account:** the callback withdraws Google's grant, stores nothing, and returns to the app with `?signin_error=not_allowed`. It also sets a two-minute cookie that only that browser reads, naming the account Google reported, so the person can see which account they used. The account is never logged or put in a URL.
4. Otherwise it connects the Channel, stores the credentials, and sets the **session** cookie.

**Session.** The cookie names the Owner's email, an expiry 30 days out, and the session epoch it was issued under, signed with HMAC-SHA256 under `YDE_SESSION_SECRET`. The epoch is a number in the Store: Disconnect bumps it, which ends every copy of every earlier session cookie, not just the one in this browser. It's HttpOnly, SameSite=Lax, and Secure on https. Apart from the epoch, nothing is kept server-side, so any serverless instance can check it. When a session secret is set, every `/api` route except health, login and callback answers 401 without a valid session for the Owner. Mutating requests still need the client header (ADR-0006), so another site can't drive the API with the Owner's cookie.

**Fail closed.** A deployment, meaning an https `YDE_PUBLIC_URL` or a session secret, doesn't start unless it has all of these:
- `YDE_SESSION_SECRET`, or the API would be open;
- `YDE_OWNER_EMAIL`, or any Google account could get in;
- `YDE_TOKEN_KEY`, or the Google token would be stored readable;
- an https address, or the cookies wouldn't be Secure.

**Credentials.** The Google credentials (with the refresh token) live in the Store, not in `data/token.json`, so they survive restarts and can be read by any instance of the app. With `YDE_TOKEN_KEY` (a Fernet key, required in the cloud) they're encrypted; locally, without a key, they're kept as plain JSON in the owner's own database file. If the stored token can't be read with the current key (the key changed), the app logs a warning and asks for a new sign-in. Disconnect withdraws the grant with Google, deletes the credentials and ends the session.

**Client.** The OAuth client must be a *Web application* client, with the app's callback as an authorised redirect URI. It comes from `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, or from `data/client_secret.json`. A *Desktop* client is no longer enough. It's a confidential client with a secret, and the `state` cookie binds the callback to the browser, so the flow skips PKCE.

**Local mode** still needs no session: it binds to 127.0.0.1 (ADR-0006). If `YDE_OWNER_EMAIL` is set locally, the same allow-list applies to the Connection.

**Consent screen.** Publishing needs a home page, a privacy policy, terms of service and an authorized domain. The app serves `privacy.html` and `terms.html` to anyone, and they're honest about what it is: one owner's tool. Publish it ("In production") without verification: the Owner clicks through Google's "unverified app" warning once, and the refresh token stops expiring after 7 days, as it does for apps in Testing.

**Rejected alternatives.**
- Vercel Deployment Protection puts a Vercel login in front of the site, but covering the production domain needs the Pro plan.
- A passphrase would be a second credential to look after, next to the Google sign-in the app needs anyway.
