"use client";

import * as React from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Sprite from "@/components/ui/Sprite";
import { labelize } from "@/lib/derive";
import type { RunEvent } from "@/types/assay";
import { ACTOR_META } from "./spanMeta";

/**
 * Detail pane for the selected span.
 *
 * The headline feature: when the event is `response_graded` we render the
 * grader's reasoning as a readable "judge verdict" card (score / passed /
 * matched / missed / forbidden / feedback) — the Braintrust pattern where the
 * scoring span surfaces *why* a judgment was made, not a raw JSON dump. Every
 * other span gets a clean key/value summary plus a collapsible payload.
 */
export type SpanDetailProps = {
  span: RunEvent | null;
};

type Check = { id?: string; label?: string; keyword?: string; reason?: string };

function asString(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

function asChecks(value: unknown): Check[] {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => {
    if (typeof entry === "string") return { label: entry };
    if (entry && typeof entry === "object") return entry as Check;
    return { label: String(entry) };
  });
}

function checkLabel(check: Check): string {
  return check.label ?? check.id ?? check.keyword ?? asString(check);
}

function formatMs(value: unknown): string | null {
  const ms = asNumber(value);
  return ms === null ? null : `${ms.toFixed(0)} ms`;
}

export function SpanDetail({ span }: SpanDetailProps) {
  if (!span) {
    return (
      <div
        style={{
          height: "100%",
          display: "grid",
          placeItems: "center",
          padding: 24,
          textAlign: "center",
          color: "var(--color-fg-muted)"
        }}
      >
        <div style={{ display: "grid", gap: 8, justifyItems: "center" }}>
          <Sprite name="timeline-node" sheet="runs" scale={1.4} />
          <p style={{ margin: 0, fontSize: 13 }}>Select a span to inspect its payload.</p>
        </div>
      </div>
    );
  }

  const meta = ACTOR_META[span.actor] ?? ACTOR_META.system;
  const isGraded = span.event_type === "response_graded";

  return (
    <div style={{ display: "grid", gap: 12, padding: 16, overflowY: "auto", height: "100%" }}>
      <header style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span
            aria-hidden="true"
            style={{
              width: 10,
              height: 10,
              borderRadius: 999,
              background: meta.color,
              flex: "0 0 auto"
            }}
          />
          <strong style={{ fontSize: 14 }}>{labelize(span.event_type)}</strong>
          <Badge variant="neutral">{meta.label}</Badge>
          <span style={{ fontSize: 11, color: "var(--color-fg-muted)" }}>span #{span.sequence}</span>
        </div>
        <SpanTimingRow span={span} />
      </header>

      {isGraded ? <JudgeVerdict span={span} /> : <PayloadView payload={span.payload} />}
    </div>
  );
}

function SpanTimingRow({ span }: { span: RunEvent }) {
  const latency = formatMs(span.payload.latency_ms);
  const tokens = asNumber(span.payload.tokens);
  const step = span.tracerazor_step_id;
  const pieces: Array<{ label: string; value: string }> = [];
  if (latency) pieces.push({ label: "latency", value: latency });
  if (tokens !== null) pieces.push({ label: "tokens", value: String(tokens) });
  if (step !== null && step !== undefined) pieces.push({ label: "TR step", value: String(step) });
  if (pieces.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {pieces.map((piece) => (
        <span key={piece.label} style={{ fontSize: 11, color: "var(--color-fg-muted)" }}>
          {piece.label}: <strong style={{ color: "var(--color-fg)" }}>{piece.value}</strong>
        </span>
      ))}
    </div>
  );
}

/** The Braintrust-style "judge verdict" surface for a `response_graded` span. */
function JudgeVerdict({ span }: { span: RunEvent }) {
  const payload = span.payload;
  const passed = payload.passed === true;
  const score = asNumber(payload.score);
  const competency = asString(payload.competency);
  const variant = asString(payload.variant);
  const matched = asChecks(payload.matched_checks);
  const missed = asChecks(payload.missed_checks);
  const forbidden = asChecks(payload.forbidden_hits);
  const feedback = asString(payload.feedback);

  return (
    <Card aria-label="grader verdict" style={{ overflow: "hidden" }}>
      <CardHeader
        style={{
          background: passed ? "var(--color-pass-bg)" : "var(--color-warn-bg)",
          borderBottom: "1px solid var(--color-border)"
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Sprite name={passed ? "grader-approve" : "grader-reject"} sheet="judging" />
          <strong style={{ fontSize: 13 }}>Judge verdict</strong>
        </span>
        <Badge variant={passed ? "pass" : "fail"}>{passed ? "passed" : "failed"}</Badge>
      </CardHeader>
      <CardBody style={{ display: "grid", gap: 12, paddingTop: 14 }}>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          <Stat label="Score" value={score === null ? "·" : score.toFixed(2)} />
          {competency && <Stat label="Competency" value={labelize(competency)} />}
          {variant && <Stat label="Variant" value={labelize(variant)} />}
        </div>

        <CheckList title="Matched checks" tone="pass" checks={matched} emptyHint="No checks matched." />
        <CheckList title="Missed checks" tone="warn" checks={missed} emptyHint="Nothing missed." />
        {forbidden.length > 0 && (
          <CheckList title="Forbidden hits" tone="fail" checks={forbidden} emptyHint="" />
        )}

        {feedback && (
          <div style={{ display: "grid", gap: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--color-fg-muted)" }}>
              Reasoning
            </span>
            <p
              style={{
                margin: 0,
                fontSize: 13,
                lineHeight: 1.5,
                color: "var(--color-fg)",
                background: "var(--color-soft)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "8px 10px",
                whiteSpace: "pre-wrap"
              }}
            >
              {feedback}
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <span style={{ fontSize: 11, color: "var(--color-fg-muted)" }}>{label}</span>
      <strong style={{ fontSize: 15 }}>{value}</strong>
    </div>
  );
}

const TONE_COLOR: Record<"pass" | "warn" | "fail", string> = {
  pass: "var(--color-pass)",
  warn: "var(--color-warn)",
  fail: "var(--color-fail)"
};

function CheckList({
  title,
  tone,
  checks,
  emptyHint
}: {
  title: string;
  tone: "pass" | "warn" | "fail";
  checks: Check[];
  emptyHint: string;
}) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <span style={{ fontSize: 11, fontWeight: 700, color: "var(--color-fg-muted)" }}>
        {title} ({checks.length})
      </span>
      {checks.length === 0 ? (
        emptyHint ? (
          <span style={{ fontSize: 12, color: "var(--color-fg-muted)" }}>{emptyHint}</span>
        ) : null
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 4 }}>
          {checks.map((check, index) => (
            <li
              key={`${checkLabel(check)}-${index}`}
              style={{
                display: "flex",
                gap: 8,
                alignItems: "baseline",
                fontSize: 12,
                lineHeight: 1.4
              }}
            >
              <span aria-hidden="true" style={{ color: TONE_COLOR[tone], flex: "0 0 auto" }}>
                {tone === "pass" ? "✓" : tone === "fail" ? "✕" : "•"}
              </span>
              <span style={{ color: "var(--color-fg)" }}>
                {checkLabel(check)}
                {check.reason ? (
                  <span style={{ color: "var(--color-fg-muted)" }}> · {check.reason}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Clean key/value rendering for non-grading spans (scalars inline, objects collapsed). */
function PayloadView({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload).filter(([key]) => key !== "latency_ms" && key !== "tokens");
  if (entries.length === 0) {
    return (
      <p style={{ margin: 0, fontSize: 13, color: "var(--color-fg-muted)" }}>
        This span carries no payload fields.
      </p>
    );
  }
  return (
    <dl style={{ margin: 0, display: "grid", gap: 8 }}>
      {entries.map(([key, value]) => {
        const isComplex = value !== null && typeof value === "object";
        return (
          <div key={key} style={{ display: "grid", gap: 2 }}>
            <dt style={{ fontSize: 11, fontWeight: 700, color: "var(--color-fg-muted)" }}>
              {labelize(key)}
            </dt>
            <dd style={{ margin: 0 }}>
              {isComplex ? (
                <pre
                  style={{
                    margin: 0,
                    fontSize: 12,
                    lineHeight: 1.45,
                    background: "var(--color-soft)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-md)",
                    padding: "8px 10px",
                    overflowX: "auto",
                    color: "var(--color-fg)"
                  }}
                >
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <span style={{ fontSize: 13, color: "var(--color-fg)", wordBreak: "break-word" }}>
                  {asString(value) || "·"}
                </span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export default SpanDetail;
