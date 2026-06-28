"use client";

import * as React from "react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Sprite } from "@/components/ui/Sprite";
import { useRunComparison } from "@/lib/queries";
import { errorMessage, labelize } from "@/lib/derive";
import type { ComparisonOutcome, CompetencyComparison, RunComparison as RunComparisonData } from "@/types/assay";

/** Delta-cell shading per LangSmith's improved/regressed/unchanged pattern. */
const DELTA_STYLE: Record<ComparisonOutcome, React.CSSProperties> = {
  improved: { background: "var(--color-pass-bg)", color: "var(--color-pass)" },
  new: { background: "var(--color-pass-bg)", color: "var(--color-pass)" },
  regressed: { background: "var(--color-fail-bg)", color: "var(--color-fail)" },
  dropped: { background: "var(--color-fail-bg)", color: "var(--color-fail)" },
  unchanged: { background: "transparent", color: "var(--color-fg-muted)" }
};

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function signedPct(value: number) {
  const rounded = Math.round(value * 100);
  if (rounded > 0) return `+${rounded}%`;
  if (rounded < 0) return `${rounded}%`;
  return "0%";
}

export type RunComparisonProps = {
  /** Current run being compared. */
  runId: string | null | undefined;
  /** Explicit baseline run id; defaults to the run's recorded prior run. */
  baseline?: string;
  /** Optional pre-fetched comparison. When provided the hook is skipped. */
  comparison?: RunComparisonData;
  className?: string;
};

/**
 * Two-run side-by-side: one row per competency with baseline vs current scores
 * and a shaded delta cell, plus improved/regressed/unchanged tallies and a
 * certified-changed note.
 */
export function RunComparison({ runId, baseline, comparison: provided, className }: RunComparisonProps) {
  const query = useRunComparison(provided ? null : runId, baseline);
  const comparison = provided ?? query.data;
  const isLoading = !provided && query.isLoading;
  const error = !provided ? query.error : null;

  const header = (
    <CardHeader>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <Sprite name="run-complete" sheet="runs" aria-hidden="true" />
        <span style={{ fontWeight: 700 }}>Run comparison</span>
      </span>
      {comparison && comparison.baseline_run_id ? (
        <span style={{ display: "inline-flex", gap: 6 }}>
          <Badge variant="pass" aria-label={`${comparison.improved} improved`}>↑ {comparison.improved}</Badge>
          <Badge variant="fail" aria-label={`${comparison.regressed} regressed`}>↓ {comparison.regressed}</Badge>
          <Badge variant="neutral" aria-label={`${comparison.unchanged} unchanged`}>= {comparison.unchanged}</Badge>
        </span>
      ) : null}
    </CardHeader>
  );

  if (isLoading) {
    return (
      <Card className={className} aria-busy="true">
        {header}
        <CardBody>
          <div className="ws-skeleton-row" style={{ height: 72 }} aria-hidden="true" />
        </CardBody>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        {header}
        <CardBody>
          <p role="alert" style={{ color: "var(--color-fail)", fontSize: 13, margin: 0 }}>
            Could not load comparison: {errorMessage(error)}
          </p>
        </CardBody>
      </Card>
    );
  }

  if (!comparison || !comparison.baseline_run_id || comparison.competencies.length === 0) {
    return (
      <Card className={className}>
        {header}
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
              No prior run to compare against yet. Run this candidate again to see how each competency moved.
            </p>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className={className}>
      {header}
      <CardBody>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <caption className="sr-only">
            Competency scores comparing run {comparison.run_id} against baseline {comparison.baseline_run_id}
          </caption>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--color-fg-muted)", fontSize: 11, textTransform: "uppercase" }}>
              <th style={{ padding: "6px 8px", fontWeight: 600 }} scope="col">
                Competency
              </th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }} scope="col">
                Baseline
              </th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }} scope="col">
                Current
              </th>
              <th style={{ padding: "6px 8px", fontWeight: 600, textAlign: "right" }} scope="col">
                Delta
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.competencies.map((row) => (
              <ComparisonRow key={row.competency} row={row} />
            ))}
          </tbody>
        </table>

        {comparison.certified_changed ? (
          <p
            style={{
              margin: "12px 0 0",
              padding: "8px 10px",
              borderRadius: "var(--radius-md)",
              background: "var(--color-warn-bg)",
              color: "var(--color-warn)",
              fontSize: 12,
              fontWeight: 600
            }}
          >
            Certification status changed between these runs.
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function ComparisonRow({ row }: { row: CompetencyComparison }) {
  const deltaStyle = DELTA_STYLE[row.outcome] ?? DELTA_STYLE.unchanged;
  return (
    <tr style={{ borderTop: "1px solid var(--color-border)" }}>
      <th
        scope="row"
        style={{ padding: "8px", fontWeight: 600, color: "var(--color-fg)", textAlign: "left" }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          {row.label || labelize(row.competency)}
          {row.current_passed ? (
            <Sprite name="grader-approve" sheet="judging" aria-hidden="true" />
          ) : (
            <Sprite name="grader-reject" sheet="judging" aria-hidden="true" />
          )}
        </span>
      </th>
      <td style={{ padding: "8px", textAlign: "right", color: "var(--color-fg-muted)" }}>
        {pct(row.baseline_score)}
      </td>
      <td style={{ padding: "8px", textAlign: "right", color: "var(--color-fg)" }}>{pct(row.current_score)}</td>
      <td style={{ padding: "8px", textAlign: "right" }}>
        <span
          aria-label={`${labelize(row.outcome)}, ${signedPct(row.delta)}`}
          style={{
            display: "inline-block",
            minWidth: 52,
            padding: "2px 8px",
            borderRadius: "var(--radius-pill)",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            ...deltaStyle
          }}
        >
          {signedPct(row.delta)}
        </span>
      </td>
    </tr>
  );
}

export default RunComparison;
