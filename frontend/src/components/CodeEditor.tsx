"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Skeleton } from "./ui";

const Monaco = dynamic(() => import("@monaco-editor/react").then((m) => m.default), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-64 w-full" />,
});

export const MONACO_LANG: Record<string, string> = {
  python: "python", cpp: "cpp", java: "java", javascript: "javascript", sql: "sql",
};

function useDark() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const el = document.documentElement;
    const sync = () => setDark(el.classList.contains("dark"));
    sync();
    const obs = new MutationObserver(sync);
    obs.observe(el, { attributes: true, attributeFilter: ["class"] });
    return () => obs.disconnect();
  }, []);
  return dark;
}

export function CodeEditor({ language, value, onChange, height = "100%", readOnly }: {
  language: string; value: string; onChange: (v: string) => void; height?: string | number; readOnly?: boolean;
}) {
  const dark = useDark();
  return (
    <Monaco
      height={height}
      language={MONACO_LANG[language] ?? "plaintext"}
      theme={dark ? "vs-dark" : "light"}
      value={value}
      onChange={(v) => onChange(v ?? "")}
      options={{
        readOnly,
        fontSize: 13,
        fontFamily: "var(--font-plex-mono), ui-monospace, monospace",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        tabSize: language === "python" ? 4 : 2,
        automaticLayout: true,
        padding: { top: 10 },
        renderLineHighlight: "line",
        lineNumbersMinChars: 3,
      }}
    />
  );
}
