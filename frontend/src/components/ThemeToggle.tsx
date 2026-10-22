import { useEffect, useState } from "react";
import { applyTheme, readSavedTheme, resolveTheme, saveTheme, type Theme } from "../lib/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() =>
    resolveTheme(readSavedTheme(), window.matchMedia("(prefers-color-scheme: dark)").matches),
  );

  useEffect(() => applyTheme(theme), [theme]);

  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        saveTheme(next);
        setTheme(next);
      }}
      className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-fg"
      aria-label={`Switch to ${next} mode`}
    >
      {theme === "dark" ? "☀ Light" : "☾ Dark"}
    </button>
  );
}
