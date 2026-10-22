import type { AuthStatus } from "../api/auth";
import { useConnect, useDisconnect } from "../api/auth";

export function ConnectScreen({ status }: { status: AuthStatus }) {
  const connect = useConnect();
  const disconnect = useDisconnect();

  if (status.state === "no_client_secret") {
    return (
      <Card title="Add your Google OAuth client">
        <p className="text-muted">
          The app needs your own Desktop OAuth client to talk to YouTube. Create one in Google Cloud (see the README's{" "}
          <em>Google Cloud setup</em>), download it, and save it as:
        </p>
        <code className="mt-3 block rounded-md bg-bg px-3 py-2 text-sm">data/client_secret.json</code>
        <p className="mt-3 text-sm text-muted">Then reload this page. The file stays on your machine and is never committed.</p>
      </Card>
    );
  }

  const expired = status.state === "expired";
  return (
    <Card title={expired ? "Your Google sign-in expired" : "Connect your YouTube channel"}>
      <p className="text-muted">
        {expired
          ? "Google sign-ins for apps in Testing mode last 7 days. Sign in again to continue; your history and backups are kept."
          : "Sign in with the Google account that owns your channel. Only this computer gets access, and you can disconnect at any time."}
      </p>
      <button
        type="button"
        onClick={() => connect.mutate()}
        disabled={connect.isPending}
        className="mt-6 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-on-accent hover:opacity-90 disabled:opacity-60"
      >
        <GoogleMark />
        {connect.isPending ? "Waiting for Google…" : expired ? "Sign in again" : "Sign in with Google"}
      </button>
      {connect.isPending && (
        <p className="mt-3 text-sm text-muted" role="status">
          Finish signing in in the browser tab Google opened. This page updates automatically.
          <br />
          If Google says <em>Access blocked</em>, add your Google account as a test user on the OAuth consent
          screen (see the README), then try again after this times out (3 minutes).
        </p>
      )}
      {expired && !connect.isPending && (
        <button
          type="button"
          onClick={() => disconnect.mutate()}
          disabled={disconnect.isPending}
          className="ml-4 text-sm text-muted underline-offset-2 hover:text-fg hover:underline"
        >
          Forget this sign-in
        </button>
      )}
      {connect.isError && (
        <p className="mt-3 text-sm text-danger" role="alert">
          {connect.error.message}
        </p>
      )}
    </Card>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mx-auto max-w-lg rounded-xl border border-line bg-surface p-8 shadow-sm">
      <h2 className="mb-2 text-lg font-semibold">{title}</h2>
      {children}
    </section>
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
