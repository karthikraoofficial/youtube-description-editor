import { useState } from "react";
import type { ChannelInfo } from "../api/auth";
import { useDisconnect } from "../api/auth";
import { initials } from "../lib/initials";

export function Avatar({ channel, size = 28 }: { channel: ChannelInfo; size?: number }) {
  const [broken, setBroken] = useState(false);
  const style = { width: size, height: size };
  if (channel.avatar_url && !broken) {
    return (
      <img
        src={channel.avatar_url}
        alt=""
        style={style}
        className="rounded-full object-cover"
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <span
      style={style}
      className="inline-flex items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent"
      aria-hidden
    >
      {initials(channel.title)}
    </span>
  );
}

export function ChannelBadge({ channel }: { channel: ChannelInfo }) {
  const disconnect = useDisconnect();
  return (
    <div className="flex items-center gap-2.5">
      <Avatar channel={channel} />
      <span className="hidden max-w-48 truncate text-sm font-medium sm:inline" title={channel.title}>
        {channel.title}
      </span>
      <button
        type="button"
        onClick={() => {
          if (confirm("Disconnect this channel? The saved Google sign-in will be revoked.")) disconnect.mutate();
        }}
        disabled={disconnect.isPending}
        className="rounded-md px-2 py-1 text-sm text-muted hover:bg-line/60 hover:text-fg disabled:opacity-50"
      >
        {disconnect.isPending ? "Disconnecting…" : "Disconnect"}
      </button>
    </div>
  );
}
