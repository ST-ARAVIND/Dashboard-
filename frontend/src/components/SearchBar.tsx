import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { SearchResult } from "../api/types";

export function SearchBar() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 1) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await api.search(q.trim());
        setResults(r.results);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const pick = (r: SearchResult) => {
    setOpen(false);
    setQ("");
    nav(`/symbol/${r.token}`);
  };

  return (
    <div className="relative" ref={boxRef}>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Search NIFTY, RELIANCE, BANKNIFTY…"
        className="w-full bg-bg-soft border border-line rounded px-3 py-1.5 text-[13px] outline-none focus:border-accent"
      />
      {open && results.length > 0 && (
        <div className="absolute mt-1 w-full bg-bg-panel border border-line rounded shadow-xl max-h-80 overflow-auto z-30">
          {results.map((r) => (
            <button
              key={`${r.token}-${r.exch_seg}`}
              onClick={() => pick(r)}
              className="w-full text-left px-3 py-1.5 hover:bg-bg-soft flex justify-between items-center"
            >
              <span className="font-mono text-ink">{r.symbol}</span>
              <span className="text-[11px] text-muted">
                {r.exch_seg} · {r.instrumenttype || "EQ"}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
