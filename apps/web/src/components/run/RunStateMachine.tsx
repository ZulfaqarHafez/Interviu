"use client";

import * as React from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Sprite from "@/components/ui/Sprite";
import { labelize } from "@/lib/derive";
import type { RunEvent } from "@/types/assay";
import type { RunStreamStatus } from "@/lib/useRunStream";

/**
 * Visual surface for `useRunStream`: a determinate progress bar, the current
 * state label, a live list of graded cases as they arrive, and a Cancel button
 * (enabled only while the run is in flight). Sprites carry the status accent.
 */
export type RunStateMachineProps = {
  status: RunStreamStatus;
  progress: number;
  gradedCount: number;
  totalExpected: number;
  events: RunEvent[];
  onCancel: () => void;
};

const STATUS_META: Record<
  RunStreamStatus,
  { label: string; badge: "pass" | "warn" | "fail" | "neutral"; sprite: string; sheet: "runs" | "judging"; thinking: boolean }
> = {
  idle: { label: "Idle", badge: "neutral", sprite: "run-queued", sheet: "runs", thinking: false },
  queued: { label: "Queued", badge: "neutral", sprite: "run-queued", sheet: "runs", thinking: true },
  running: { label: "Running", badge: "warn", sprite: "run-running", sheet: "runs", thinking: true },
  completed: { label: "Completed", badge: "pass", sprite: "run-complete", sheet: "runs", thinking: false },
  failed: { label: "Failed", badge: "fail", sprite: "fail-bead", sheet: "runs", thinking: false },
  canceled: { label: "Canceled", badge: "neutral", sprite: "run-queued", sheet: "runs", thinking: false }
};

type GradedCase = {
  spanId: string;
  competency: string;
  passed: boolean;
  score: number | null;
};

function gradedCases(events: RunEvent[]): GradedCase[] {
  return events
    .filter((event) => event.event_type === "response_graded")
    .sort((a, b) => a.sequence - b.sequence)
    .map((event) => ({
      spanId: event.span_id,
      competency: String(event.payload.competency ?? "case"),
      passed: event.payload.passed === true,
      score: typeof event.payload.score === "number" ? event.payload.score : null
    }));
}

export function RunStateMachine({
  status,
  progress,
  gradedCount,
  totalExpected,
  events,
  onCancel
}: RunStateMachineProps) {
  const meta = STATUS_META[status];
  const cases = React.useMemo(() => gradedCases(events), [events]);
  const isActive = status === "queued" || status === "running";
  const determinate = totalExpected > 0;
  const pct = Math.round((determinate ? progress : isActive ? 0 : 1) * 100);
  const progressLabel = determinate
    ? `${gradedCount} / ${totalExpected} cases graded`
    : `${gradedCount} case${gradedCount === 1 ? "" : "s"} graded`;

  return (
    <Card aria-label="Run progress">
      <CardHeader>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Sprite name={meta.sprite} sheet={meta.sheet} thinking={meta.thinking} />
          <strong style={{ fontSize: 13 }}>Evaluation run</strong>
          <Badge variant={meta.badge}>{meta.label}</Badge>
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={!isActive}
          aria-label="Cancel run"
        >
          Cancel
        </Button>
      </CardHeader>
      <CardBody style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "grid", gap: 6 }}>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={determinate ? 100 : undefined}
            aria-valuenow={determinate ? pct : undefined}
            aria-valuetext={determinate ? `${pct}%` : progressLabel}
            aria-label="Run progress"
            style={{
              height: 8,
              borderRadius: "var(--radius-pill)",
              background: "var(--color-soft)",
              overflow: "hidden",
              border: "1px solid var(--color-border)"
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${pct}%`,
                background:
                  status === "failed"
                    ? "var(--color-fail)"
                    : status === "completed"
                      ? "var(--color-pass)"
                      : "var(--color-accent)",
                transition: "width 240ms ease"
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: "var(--color-fg-muted)" }}>{progressLabel}</span>
        </div>

        <div style={{ display: "grid", gap: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--color-fg-muted)" }}>
            Graded cases
          </span>
          {cases.length === 0 ? (
            <span style={{ fontSize: 12, color: "var(--color-fg-muted)" }}>
              {isActive ? "Waiting for the first grade…" : "No cases graded yet."}
            </span>
          ) : (
            <ul
              aria-live="polite"
              style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 4, maxHeight: 180, overflowY: "auto" }}
            >
              {cases.map((item) => (
                <li
                  key={item.spanId}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    padding: "6px 8px",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--color-border)",
                    background: "var(--color-surface)",
                    fontSize: 12
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span
                      aria-hidden="true"
                      style={{ color: item.passed ? "var(--color-pass)" : "var(--color-fail)" }}
                    >
                      {item.passed ? "✓" : "✕"}
                    </span>
                    {labelize(item.competency)}
                  </span>
                  {item.score !== null && (
                    <span style={{ color: "var(--color-fg-muted)", fontVariantNumeric: "tabular-nums" }}>
                      {item.score.toFixed(2)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

export default RunStateMachine;
