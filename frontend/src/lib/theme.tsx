"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

// Inlined in <head> so the correct theme is applied before first paint.
export const themeInitScript = `(function(){try{var t=localStorage.getItem('pp-theme');if(!t){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}if(t==='dark')document.documentElement.classList.add('dark')}catch(e){}})();`;

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    try { localStorage.setItem("pp-theme", next); } catch { /* storage unavailable */ }
    setTheme(next);
  };

  return { theme, toggle };
}
