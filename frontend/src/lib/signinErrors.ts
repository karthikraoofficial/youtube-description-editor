/** What the sign-in callback's `?signin_error=<reason>` means, in words (ADR-0019). */
const MESSAGES: Record<string, string> = {
  no_client_secret: "The app has no Google OAuth client yet. See the README's Google Cloud setup.",
  state: "That sign-in link was stale or came from another tab. Try signing in again.",
  access_denied: "Sign-in was cancelled on Google's page.",
  not_allowed: "That Google account isn't allowed to use this app. Sign in with the account that owns it.",
  channel: "Signed in, but the account's YouTube channel couldn't be loaded. Check it has a channel, then try again.",
  google: "Google didn't complete the sign-in. Try again.",
};

export function signInErrorFrom(search: string): string | null {
  const code = new URLSearchParams(search).get("signin_error");
  if (code === null) return null;
  return MESSAGES[code] ?? "Sign-in didn't complete. Try again.";
}

const REFUSED_COOKIE = "yde_refused_account";

/** The account Google reported for a refused sign-in, from the one-off cookie the callback sets (ADR-0019). */
export function refusedAccountFrom(cookies: string): string | null {
  const entry = cookies.split("; ").find((c) => c.startsWith(`${REFUSED_COOKIE}=`));
  return entry ? decodeURIComponent(entry.slice(REFUSED_COOKIE.length + 1)) : null;
}

/** Forget it once shown. */
export function clearRefusedAccount(): void {
  document.cookie = `${REFUSED_COOKIE}=; Max-Age=0; Path=/`;
}
