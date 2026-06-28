"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  FlaskConical, Layers, Bot, Beaker, Clock, MoonStar, CheckCircle2, AlertTriangle, CornerDownLeft
} from "lucide-react";
import { useRuns, useExamPacks, useCandidates } from "@/lib/queries";

type Item = {
  id: string;
  label: string;
  sublabel?: string;
  group: string;
  icon: React.ReactNode;
  run: () => void;
};

/**
 * Keyboard-first command palette (⌘K / Ctrl-K). Jumps to any route, recent run,
 * suite, or agent, plus quick actions. Mounted once under the providers so its
 * data hooks share the workspace query cache.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [active, setActive] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const listRef = React.useRef<HTMLDivElement>(null);

  const runsQuery = useRuns();
  const packsQuery = useExamPacks();
  const candidatesQuery = useCandidates();
  const runs = React.useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const packs = React.useMemo(() => packsQuery.data ?? [], [packsQuery.data]);
  const candidates = React.useMemo(() => candidatesQuery.data ?? [], [candidatesQuery.data]);

  const nameById = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of candidates) m[c.id] = c.name;
    return m;
  }, [candidates]);

  const go = React.useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router]
  );

  const toggleTheme = React.useCallback(() => {
    const isDark = document.documentElement.classList.toggle("dark");
    try {
      localStorage.setItem("assay-theme", isDark ? "dark" : "light");
    } catch {
      /* ignore */
    }
    setOpen(false);
  }, []);

  // The full candidate item set, grouped. Filtered below by query.
  const items = React.useMemo<Item[]>(() => {
    const nav: Item[] = [
      { id: "nav-test", label: "Test an agent", sublabel: "Run a new litmus test", group: "Go to", icon: <FlaskConical size={15} />, run: () => go("/") },
      { id: "nav-runs", label: "Experiments", sublabel: "All runs, scored", group: "Go to", icon: <Beaker size={15} />, run: () => go("/runs") },
      { id: "nav-suites", label: "Suites", sublabel: "Adversarial test datasets", group: "Go to", icon: <Layers size={15} />, run: () => go("/suites") },
      { id: "nav-agents", label: "Agents", sublabel: "Agents under test", group: "Go to", icon: <Bot size={15} />, run: () => go("/agents") }
    ];
    const actions: Item[] = [
      { id: "act-theme", label: "Toggle theme", sublabel: "Light / dark", group: "Actions", icon: <MoonStar size={15} />, run: toggleTheme }
    ];
    const runItems: Item[] = runs.slice(0, 12).map((r) => {
      const scored = r.status === "completed" && typeof r.certified === "boolean";
      return {
        id: `run-${r.id}`,
        label: nameById[r.candidate_id] ?? r.candidate_id,
        sublabel: `${r.id} · ${r.exam_pack_id}`,
        group: "Recent runs",
        icon: scored ? (r.certified ? <CheckCircle2 size={15} color="var(--color-pass)" /> : <AlertTriangle size={15} color="var(--color-warn)" />) : <Clock size={15} />,
        run: () => go(`/runs/${r.id}`)
      };
    });
    const suiteItems: Item[] = packs.map((p) => ({
      id: `suite-${p.id}`,
      label: p.name,
      sublabel: `${p.id} · ${p.items.length} probes`,
      group: "Suites",
      icon: <Layers size={15} />,
      run: () => go("/suites")
    }));
    return [...nav, ...actions, ...runItems, ...suiteItems];
  }, [runs, packs, nameById, go, toggleTheme]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => `${it.label} ${it.sublabel ?? ""}`.toLowerCase().includes(q));
  }, [items, query]);

  // Group preserving order of first appearance.
  const groups = React.useMemo(() => {
    const order: string[] = [];
    const map = new Map<string, Item[]>();
    for (const it of filtered) {
      if (!map.has(it.group)) {
        map.set(it.group, []);
        order.push(it.group);
      }
      map.get(it.group)!.push(it);
    }
    return order.map((g) => ({ group: g, items: map.get(g)! }));
  }, [filtered]);

  // Global open shortcut + escape.
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    function onOpen() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("assay:open-cmdk", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("assay:open-cmdk", onOpen);
    };
  }, []);

  // Reset + focus when opening.
  React.useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      const t = setTimeout(() => inputRef.current?.focus(), 20);
      return () => clearTimeout(t);
    }
  }, [open]);

  React.useEffect(() => {
    setActive(0);
  }, [query]);

  if (!open) return null;

  function onInputKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      filtered[active]?.run();
    }
  }

  let runningIndex = -1;

  return (
    <div className="cmdk-overlay" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={() => setOpen(false)}>
      <div className="cmdk-panel" onMouseDown={(e) => e.stopPropagation()}>
        <div className="cmdk-input-row">
          <input
            ref={inputRef}
            className="cmdk-input"
            placeholder="Jump to a run, suite, agent, or action…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            aria-label="Command palette search"
          />
          <kbd className="cmdk-esc">esc</kbd>
        </div>
        <div className="cmdk-list" ref={listRef}>
          {filtered.length === 0 ? (
            <div className="cmdk-empty">No matches for “{query}”.</div>
          ) : (
            groups.map((g) => (
              <div className="cmdk-group" key={g.group}>
                <div className="cmdk-group-label">{g.group}</div>
                {g.items.map((it) => {
                  runningIndex += 1;
                  const idx = runningIndex;
                  return (
                    <button
                      type="button"
                      key={it.id}
                      className={`cmdk-item ${idx === active ? "active" : ""}`}
                      onMouseEnter={() => setActive(idx)}
                      onClick={() => it.run()}
                    >
                      <span className="cmdk-item-icon">{it.icon}</span>
                      <span className="cmdk-item-text">
                        <span className="cmdk-item-label">{it.label}</span>
                        {it.sublabel ? <span className="cmdk-item-sub">{it.sublabel}</span> : null}
                      </span>
                      {idx === active ? <CornerDownLeft size={13} className="cmdk-item-enter" /> : null}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
