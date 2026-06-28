"use client";

import * as React from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip
} from "recharts";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Sprite } from "@/components/ui/Sprite";
import { labelize } from "@/lib/derive";
import type { Scorecard } from "@/types/assay";

export type CompetencyRadarProps = {
  /** Full scorecard; `competency_scores` is read for the radar. */
  scorecard?: Scorecard | null;
  /** Or pass a competency→score (0..1) map directly. */
  competencyScores?: Record<string, number>;
  /** Optional pass threshold (0..1) drawn as the breakdown bar target. */
  threshold?: number;
  className?: string;
};

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

/**
 * Competency radar/spider chart as the scorecard hero, with a per-competency
 * breakdown list below. Drop-in replacement for the zero-filled bar list in
 * page.tsx — shows a real empty state when there are no scores instead of
 * rendering a flat zero ring.
 */
export function CompetencyRadar({ scorecard, competencyScores, threshold, className }: CompetencyRadarProps) {
  const scores = competencyScores ?? scorecard?.competency_scores ?? {};
  const passAtK = scorecard?.pass_at_k ?? {};
  const passThreshold = threshold ?? scorecard?.thresholds?.competency ?? 0.8;

  const entries = Object.entries(scores);
  const hasScores = entries.length > 0;

  const header = (
    <CardHeader>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <Sprite name="grader-deliberating" sheet="judging" aria-hidden="true" />
        <span style={{ fontWeight: 700 }}>Competency scores</span>
      </span>
      {scorecard ? (
        <Badge variant={scorecard.certified ? "pass" : "warn"}>
          {scorecard.certified ? "Certified" : "Needs review"}
        </Badge>
      ) : null}
    </CardHeader>
  );

  if (!hasScores) {
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
              padding: "28px 8px",
              textAlign: "center"
            }}
          >
            <Sprite name="grader-deliberating" sheet="judging" scale={2} aria-hidden="true" />
            <p style={{ color: "var(--color-fg-muted)", fontSize: 13, margin: 0, maxWidth: 320 }}>
              Run an evaluation to see competency scores.
            </p>
          </div>
        </CardBody>
      </Card>
    );
  }

  const radarData = entries.map(([competency, score]) => ({
    competency,
    label: labelize(competency),
    score: Math.round(score * 100)
  }));

  return (
    <Card className={className}>
      {header}
      <CardBody>
        <div style={{ width: "100%", height: 260 }} aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="72%">
              <PolarGrid stroke="var(--color-border)" />
              <PolarAngleAxis dataKey="label" tick={{ fill: "var(--color-fg-muted)", fontSize: 11 }} />
              <PolarRadiusAxis
                domain={[0, 100]}
                tick={{ fill: "var(--color-fg-muted)", fontSize: 10 }}
                stroke="var(--color-border)"
              />
              <Radar
                name="Score"
                dataKey="score"
                stroke="var(--color-accent)"
                fill="var(--color-accent)"
                fillOpacity={0.25}
                strokeWidth={2}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-panel)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                  color: "var(--color-fg)",
                  fontSize: 12
                }}
                formatter={(value: number | string) => [`${value}%`, "Score"]}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Per-competency breakdown list (also the accessible equivalent). */}
        <ul
          aria-label="Competency breakdown"
          style={{ listStyle: "none", margin: "8px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 8 }}
        >
          {entries.map(([competency, score]) => {
            const passed = passAtK[competency] ?? score >= passThreshold;
            return (
              <li key={competency} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--color-fg)" }}>
                    <Sprite name={passed ? "grader-approve" : "grader-reject"} sheet="judging" aria-hidden="true" />
                    {labelize(competency)}
                  </span>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <strong style={{ fontSize: 13, fontVariantNumeric: "tabular-nums", color: "var(--color-fg)" }}>
                      {pct(score)}
                    </strong>
                    <Badge variant={passed ? "pass" : "fail"}>{passed ? "Pass" : "Fail"}</Badge>
                  </span>
                </div>
                <div
                  role="meter"
                  aria-label={`${labelize(competency)} score`}
                  aria-valuenow={Math.round(score * 100)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  style={{
                    height: 6,
                    borderRadius: "var(--radius-pill)",
                    background: "var(--color-soft)",
                    overflow: "hidden"
                  }}
                >
                  <div
                    style={{
                      width: `${Math.min(100, Math.max(0, Math.round(score * 100)))}%`,
                      height: "100%",
                      background: passed ? "var(--color-pass)" : "var(--color-warn)"
                    }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </CardBody>
    </Card>
  );
}

export default CompetencyRadar;
