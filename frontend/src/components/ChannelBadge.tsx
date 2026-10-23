import { LogOut } from "lucide-react";
import { useState } from "react";
import type { ChannelInfo } from "../api/auth";
import { useDisconnect } from "../api/auth";
import { initials } from "../lib/initials";
import { Button } from "./ui/Button";

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

/** The signed-in Channel with a Disconnect button, like a user card at the foot of the sidebar. */
export function ChannelBadge({ channel }: { channel: ChannelInfo }) {
  const disconnect = useDisconnect();
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <Avatar channel={channel} size={32} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium" title={channel.title}>
          {channel.title}
        </span>
        <span className="block truncate text-xs text-muted">YouTube channel</span>
      </span>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => {
          if (confirm("Disconnect this channel? The saved Google sign-in will be revoked.")) disconnect.mutate();
        }}
        disabled={disconnect.isPending}
        aria-label={disconnect.isPending ? "Disconnecting…" : "Disconnect"}
        title="Disconnect this channel"
      >
        <LogOut aria-hidden className="size-4" />
      </Button>
    </div>
  );
}
