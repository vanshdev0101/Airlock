import { useCallback, useEffect, useState } from "react";

const KEY = "repoguard-theme";

/** Stored choice wins; otherwise follow the OS. */
function initialTheme() {
  const stored = localStorage.getItem(KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function useTheme() {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(KEY, theme);
  }, [theme]);

  // Keep following the OS until the user makes an explicit choice.
  useEffect(() => {
    if (localStorage.getItem(KEY)) return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = (e) => setTheme(e.matches ? "light" : "dark");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    []
  );

  return { theme, toggle };
}
