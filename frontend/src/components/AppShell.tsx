import { CircleHelp, History, LayoutList, Menu, PenLine, X } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import type { ChannelInfo } from "../api/auth";
import { NAV, type NavTarget, type Screen, activeNav, screenTitle } from "../lib/nav";
import { DESKTOP, useMediaQuery } from "../lib/useMediaQuery";
import { ChannelBadge } from "./ChannelBadge";
import { QuotaMeter } from "./QuotaMeter";
import { ThemeToggle } from "./ThemeToggle";
import { Badge } from "./ui/Badge";
import { Button, VARIANT } from "./ui/Button";

type Props = {
  screen: Screen;
  runFrom: NavTarget;
  onNavigate: (target: NavTarget) => void;
  /** Null while signed out: then there's no nav, only the brand and the theme toggle. */
  channel: ChannelInfo | null;
  fake: boolean;
  children: ReactNode;
};

/** The frame around every screen: a sidebar from 1024 px up, a top bar with a menu sheet below that. */
export function AppShell({ screen, runFrom, onNavigate, channel, fake, children }: Props) {
  const desktop = useMediaQuery(DESKTOP);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  // A sheet left open at phone width must not pop back after a trip to desktop width.
  useEffect(() => setMenuOpen(false), [desktop]);
  const closeMenu = () => {
    setMenuOpen(false);
    // The sheet unmounts rather than closing, so hand focus back to the button that opened it.
    requestAnimationFrame(() => menuButton.current?.focus());
  };
  const main = <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>;

  if (!channel)
    return (
      <Page>
        <header className="flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Brand />
          <div className="flex items-center gap-2">
            {fake && <FakeBadge />}
            <ThemeToggle />
          </div>
        </header>
        {main}
      </Page>
    );

  const nav = (
    <SidebarContent
      active={activeNav(screen, runFrom)}
      onNavigate={(target) => {
        closeMenu();
        onNavigate(target);
      }}
      channel={channel}
      fake={fake}
    />
  );

  if (desktop)
    return (
      <Page>
        <aside className="fixed inset-y-0 left-0 flex w-60 flex-col border-r border-line bg-sidebar">{nav}</aside>
        <div className="pl-60">{main}</div>
      </Page>
    );

  return (
    <Page>
      <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur sm:px-6">
        <Button
          ref={menuButton}
          variant="ghost"
          size="icon"
          onClick={() => setMenuOpen(true)}
          aria-label="Open menu"
          aria-haspopup="dialog"
          aria-expanded={menuOpen}
        >
          <Menu aria-hidden className="size-5" />
        </Button>
        <BrandMark />
        <span className="min-w-0 flex-1 truncate font-semibold">{screenTitle(screen)}</span>
        {fake && <FakeBadge />}
      </header>
      {menuOpen && <NavSheet onClose={closeMenu}>{nav}</NavSheet>}
      {main}
    </Page>
  );
}

function Page({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-bg text-fg">{children}</div>;
}

/** The phone menu: a modal panel from the left. Esc, the close button or the backdrop closes it. */
function NavSheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-label="Menu"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === dialog.current) onClose();
      }}
      className="m-0 h-full max-h-none w-72 max-w-[85vw] border-r border-line bg-sidebar p-0 text-fg shadow-xl backdrop:bg-black/40"
    >
      <div className="relative flex h-full flex-col">
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close menu" className="absolute right-3 top-4">
          <X aria-hidden className="size-5" />
        </Button>
        {children}
      </div>
    </dialog>
  );
}

const NAV_ICON: Record<NavTarget, typeof History> = { videos: LayoutList, history: History };

function SidebarContent({
  active,
  onNavigate,
  channel,
  fake,
}: {
  active: NavTarget;
  onNavigate: (target: NavTarget) => void;
  channel: ChannelInfo;
  fake: boolean;
}) {
  const item = "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium";
  const idle = VARIANT.ghost;
  return (
    <>
      <div className="px-5 pb-4 pt-5">
        <Brand />
      </div>
      <nav aria-label="Main" className="flex flex-col gap-0.5 px-3">
        {NAV.map(({ target, label }) => {
          const Icon = NAV_ICON[target];
          return (
            <button
              key={target}
              type="button"
              onClick={() => onNavigate(target)}
              aria-current={active === target ? "page" : undefined}
              className={`${item} ${active === target ? "bg-accent/10 text-accent" : idle}`}
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </button>
          );
        })}
        <a href="/how-it-works.html" target="_blank" rel="noopener" className={`${item} ${idle}`}>
          <CircleHelp aria-hidden className="size-4" />
          How it works
        </a>
      </nav>
      <div className="mt-auto space-y-4 border-t border-line p-4">
        {fake && <FakeBadge />}
        <QuotaMeter compact />
        <div className="flex items-center gap-1">
          <div className="min-w-0 flex-1">
            <ChannelBadge channel={channel} />
          </div>
          <ThemeToggle />
        </div>
      </div>
    </>
  );
}

function BrandMark() {
  return (
    <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-on-accent shadow-card" aria-hidden>
      <PenLine className="size-4" />
    </span>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark />
      <h1 className="text-sm font-semibold leading-tight tracking-tight" title="YouTube Description Editor">
        Description Editor
        <span className="block text-xs font-normal text-muted">for YouTube</span>
      </h1>
    </div>
  );
}

const FAKE_HINT = "an in-memory channel. Nothing is sent to Google.";

function FakeBadge() {
  return (
    <Badge tone="warn" title={`Fake mode: ${FAKE_HINT}`} data-fake-badge>
      Fake mode<span className="sr-only">: {FAKE_HINT}</span>
    </Badge>
  );
}
