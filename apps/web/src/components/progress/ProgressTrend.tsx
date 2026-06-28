"use client";

import * as React from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Sprite } from "@/components/ui/Sprite";
import { useCandidateProgress } from "@/lib/queries";
import { errorMessage, labelize } from "@/lib/derive";
import type { CandidateProgress } from "@/types/assay";

/**
 * Stable-ish palette for competency lines. Cycles through the semantic accent
 * tokens so series stay distinguishable in light and dark themes.
 */
const SERIES_COLORS = [
  "var(--color-accent)",
  "var(--color-info)",
  "var(--color-pass)",
  "var(--color-warn)",
  "var(--color-fail)"
] as const;

function colorFor(index: number) {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

export type ProgressTrendProps = {
  /** Candidate whose cross-run progress should be charted. */
  candidateId: string | null | undefined;
  /** Optional pre-fetched data. When provided the hook is skipped. */
  progress?: CandidateProgress;
  className?: string;
};

/**
 * Visible proof that the agent improves across runs: a per-competency line
 * chart of held-out scores over successive runs, plus pass-rate and run-count
 * stats. Empty until there are at least two runs to compare.
 */
export function ProgressTrend({ candidateId, progress: provided, className }: ProgressTrendProps) {
  const query = useCandidateProgress(provided ? null : candidateId);
  const progress = provided ?? query.data;
  const isLoading = !provided && query.isLoading;
  const error = !provided ? query.error : null;

  const headerSprite = (
    <Sprite name="learning-trend" aria-hidden="true" />
  );

  if (isLoading) {
    return (
      <Card className={className} aria-busy="true">
        <CardHeader>
          <span className="progress-trend__title">
            {headerSprite}
            <span>Learning trend</span>
          </span>
        </CardHeader>
        <CardBody>
          <div className="ws-skeleton-row" style={{ height: 72 }} aria-hidden="true" />
        </CardBody>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <span className="progress-trend__title">
            {headerSprite}
            <span>Learning trend</span>
          </span>
        </CardHeader>
        <CardBody>
          <p role="alert" style={{ color: "var(--color-fail)", fontSize: 13, margin: 0 }}>
            Could not load progress: {errorMessage(error)}
          </p>
        </CardBody>
      </Card>
    );
  }

  const runCount = progress?.run_count ?? 0;

  // Need at least two runs before a trend is meaningful.
  if (!progress || runCount < 2) {
    return (
      <Card className={className}>
        <CardHeader>
          <span className="progress-trend__title">
            {headerSprite}
            <span>Learning trend</span>
          </span>
        </CardHeader>
        <CardBody>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 10,
              padding: "20px 8px",
              textAlign: "center"
            }}
          >
            <Sprite name="run-queued" sheet="runs" scale={2} aria-hidden="true" />
            <p style={{ color: "var(--color-fg-muted)", fontSize: 13, margin: 0, maxWidth: 320 }}>
              Run this candidate at least twice to chart how held-out scores move across runs.
              {runCount === 1 ? " One run recorded so far." : ""}
            </p>
          </div>
        </CardBody>
      </Card>
    );
  }

  // Build a unified x-axis of run indices; each competency contributes a series.
  const runOrder: string[] = [];
  for (const competency of progress.competencies) {
    for (const point of competency.points) {
      if (!runOrder.includes(point.run_id)) {
        runOrder.push(point.run_id);
      }
    }
  }

  type ChartRow = { runId: string; label: string } & Record<string, number | string | null>;
  const rows: ChartRow[] = runOrder.map((runId, index) => {
    const row: ChartRow = { runId, label: `Run ${index + 1}` };
    for (const competency of progress.competencies) {
      const point = competency.points.find((candidate) => candidate.run_id === runId);
      row[competency.competency] = point ? Math.round(point.held_out_score * 100) : null;
    }
    return row;
  });

  return (
    <Card className={className}>
      <CardHeader>
        <span className="progress-trend__title" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          {headerSprite}
          <span style={{ fontWeight: 700 }}>Learning trend</span>
        </span>
        <span style={{ display: "inline-flex", gap: 16 }}>
          <Stat label="Runs" value={String(runCount)} />
          <Stat label="Pass rate" value={pct(progress.pass_rate)} />
        </span>
      </CardHeader>
      <CardBody>
        <div style={{ width: "100%", height: 240 }} aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
              <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                tick={{ fill: "var(--color-fg-muted)", fontSize: 11 }}
                stroke="var(--color-border)"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "var(--color-fg-muted)", fontSize: 11 }}
                stroke="var(--color-border)"
                tickFormatter={(value: number) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-panel)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                  color: "var(--color-fg)",
                  fontSize: 12
                }}
                formatter={(value: number | string, name: string) => [
                  value === null ? "·" : `${value}%`,
                  labelize(name)
                ]}
              />
              <Legend formatter={(value: string) => labelize(value)} wrapperStyle={{ fontSize: 11 }} />
              {progress.competencies.map((competency, index) => (
                <Line
                  key={competency.competency}
                  type="monotone"
                  dataKey={competency.competency}
                  name={competency.competency}
                  stroke={colorFor(index)}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Accessible text equivalent of the chart. */}
        <ul
          className="sr-only"
          aria-label={`Held-out score trend across ${runCount} runs for ${progress.candidate_name}`}
        >
          {progress.competencies.map((competency) => (
            <li key={competency.competency}>
              {competency.label || labelize(competency.competency)}: from {pct(competency.first_score)} to{" "}
              {pct(competency.latest_score)} ({competency.trend}).
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span style={{ display: "inline-flex", flexDirection: "column", alignItems: "flex-end", lineHeight: 1.1 }}>
      <strong style={{ fontSize: 16, color: "var(--color-fg)" }}>{value}</strong>
      <span style={{ fontSize: 10, color: "var(--color-fg-muted)", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </span>
    </span>
  );
}

export default ProgressTrend;
