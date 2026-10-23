import { CircleHelp } from "lucide-react";
import { useState } from "react";
import { buttonClass } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import type { AuthStatus } from "../api/auth";
import { startSignIn, useDisconnect } from "../api/auth";
import { clearRefusedAccount, refusedAccountFrom, signInErrorFrom } from "../lib/signinErrors";

export function ConnectScreen({ status }: { status: AuthStatus }) {
  const disconnect = useDisconnect();
  // The callback sends the browser back with ?signin_error=<reason>; show it once, then tidy the address bar.
  const [error] = useState(() => {
    const message = signInErrorFrom(window.location.search);
    if (message) window.history.replaceState(null, "", window.location.pathname);
    const account = refusedAccountFrom(document.cookie);
    clearRefusedAccount();
    return message && account ? `${message} Google signed you in as ${account}.` : message;
  });

  if (status.state === "no_client_secret") {
    return (
      <ConnectCard title="Add your Google OAuth client">
        <p className="text-muted">
          The app needs your own <em>Web application</em> OAuth client to sign you in and talk to YouTube. Create one
          in Google Cloud (see the README's <em>Google Cloud setup</em>), download it, and save it as:
        </p>
        <code className="mt-3 block rounded-lg bg-subtle px-3 py-2 text-sm">data/client_secret.json</code>
        <p className="mt-3 text-sm text-muted">Then reload this page. The file stays on your machine and is never committed.</p>
      </ConnectCard>
    );
  }

  const expired = status.state === "expired";
  const title = status.state === "signed_out" ? "Sign in" : expired ? "Your Google sign-in expired" : "Connect your YouTube channel";
  return (
    <ConnectCard title={title}>
      <p className="text-muted">
        {expired
          ? "Google no longer accepts the saved sign-in (it was withdrawn, or the app's consent screen is still in Testing). Sign in again to continue; your history and backups are kept."
          : "Sign in with the Google account that owns your channel. Only that account can use this app, and you can disconnect at any time."}
      </p>
      <div className="mt-6 flex flex-col items-start gap-3">
        <a
          href="/how-it-works.html"
          className={buttonClass("outline")}
        >
          <CircleHelp aria-hidden className="size-4" />
          How It Works
        </a>
        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={startSignIn}
            className={buttonClass("primary")}
          >
            <GoogleMark />
            {expired ? "Sign in again" : "Sign in with Google"}
          </button>
          {expired && (
            <button
              type="button"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
              className="text-sm text-muted underline-offset-2 hover:text-fg hover:underline"
            >
              Forget this sign-in
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="mt-3 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </ConnectCard>
  );
}

function ConnectCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="mx-auto mt-4 max-w-lg p-6 sm:mt-12 sm:p-8">
      <h2 className="mb-2 text-xl font-semibold tracking-tight">{title}</h2>
      {children}
      <p className="mt-6 text-xs text-muted">
        <a href="/privacy.html" className="underline-offset-2 hover:underline">Privacy Policy</a> ·{" "}
        <a href="/terms.html" className="underline-offset-2 hover:underline">Terms of Service</a>
      </p>
    </Card>
  );
}

function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden className="rounded-sm bg-white p-px">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.5 30.2 0 24 0 14.6 0 6.6 5.4 2.6 13.3l7.8 6C12.3 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4 7.1-10 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.4 28.7c-.5-1.4-.8-3-.8-4.7s.3-3.3.8-4.7l-7.8-6C.9 16.6 0 20.2 0 24s.9 7.4 2.6 10.7l7.8-6z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z" />
    </svg>
  );
}
