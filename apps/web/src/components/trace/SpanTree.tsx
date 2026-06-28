"use client";

import * as React from "react";
import { labelize } from "@/lib/derive";
import type { RunEvent } from "@/types/assay";
import { actorMeta } from "./spanMeta";

/**
 * Selectable span list, color-coded per actor. A single global toggle controls
 * whether each row shows its latency/token annotations (the payload already
 * carries `latency_ms` / `tokens`). Keyboard accessible via a roving listbox.
 */
export type SpanTreeProps = {
  events: RunEvent[];
  selectedSpanId: string | null;
  onSelect: (span: RunEvent) => void;
  showAnnotations: boolean;
  onToggleAnnotations: (next: boolean) => void;
};

function annotation(event: RunEvent): string | null {
  const latency = typeof event.payload.latency_ms === "number" ? event.payload.latency_ms : null;
  const tokens = typeof event.payload.tokens === "number" ? event.payload.tokens : null;
  const parts: string[] = [];
  if (latency !== null) parts.push(`${latency.toFixed(0)} ms`);
  if (tokens !== null) parts.push(`${tokens} tok`);
  return parts.length ? parts.join(" · ") : null;
}

export function SpanTree({
  events,
  selectedSpanId,
  onSelect,
  showAnnotations,
  onToggleAnnotations
}: SpanTreeProps) {
  const ordered = React.useMemo(
    () => [...events].sort((a, b) => a.sequence - b.sequence),
    [events]
  );

  const handleKeyDown = (event: React.KeyboardEvent<HTMLUListElement>) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    if (ordered.length === 0) return;
    const currentIndex = ordered.findIndex((span) => span.span_id === selectedSpanId);
    const delta = event.key === "ArrowDown" ? 1 : -1;
    const nextIndex =
      currentIndex === -1
        ? 0
        : Math.min(ordered.length - 1, Math.max(0, currentIndex + delta));
    onSelect(ordered[nextIndex]);
  };

  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
          padding: "10px 12px",
          borderBottom: "1px solid var(--color-border)"
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: "var(--color-fg-muted)" }}>
          {ordered.length} span{ordered.length === 1 ? "" : "s"}
        </span>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={showAnnotations}
            onChange={(event) => onToggleAnnotations(event.target.checked)}
          />
          Latency &amp; tokens
        </label>
      </div>

      {ordered.length === 0 ? (
        <p style={{ margin: 0, padding: 16, fontSize: 13, color: "var(--color-fg-muted)" }}>
          No spans recorded yet.
        </p>
      ) : (
        <ul
          role="listbox"
          aria-label="Trace spans"
          aria-activedescendant={selectedSpanId ? `span-${selectedSpanId}` : undefined}
          tabIndex={0}
          onKeyDown={handleKeyDown}
          style={{
            margin: 0,
            padding: 6,
            listStyle: "none",
            overflowY: "auto",
            minHeight: 0,
            display: "grid",
            gap: 4,
            outline: "none"
          }}
        >
          {ordered.map((event) => {
            const meta = actorMeta(event.actor);
            const selected = event.span_id === selectedSpanId;
            const annot = annotation(event);
            return (
              <li key={event.span_id} role="presentation">
                <button
                  type="button"
                  id={`span-${event.span_id}`}
                  role="option"
                  aria-selected={selected}
                  onClick={() => onSelect(event)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    display: "grid",
                    gap: 2,
                    padding: "8px 10px",
                    borderRadius: "var(--radius-md)",
                    borderStyle: "solid",
                    borderTopWidth: 1,
                    borderRightWidth: 1,
                    borderBottomWidth: 1,
                    borderTopColor: selected ? "var(--color-accent)" : "transparent",
                    borderRightColor: selected ? "var(--color-accent)" : "transparent",
                    borderBottomColor: selected ? "var(--color-accent)" : "transparent",
                    borderLeftWidth: 3,
                    borderLeftColor: meta.color,
                    background: selected ? "var(--color-soft)" : "transparent",
                    color: "var(--color-fg)",
                    cursor: "pointer",
                    font: "inherit"
                  }}
                >
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: "var(--color-fg-muted)",
                        minWidth: 18
                      }}
                    >
                      {event.sequence}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700 }}>{labelize(event.event_type)}</span>
                  </span>
                  <span style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <span style={{ fontSize: 11, color: meta.color, fontWeight: 600 }}>{meta.label}</span>
                    {showAnnotations && annot && (
                      <span style={{ fontSize: 10, color: "var(--color-fg-muted)", fontVariantNumeric: "tabular-nums" }}>
                        {annot}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default SpanTree;
