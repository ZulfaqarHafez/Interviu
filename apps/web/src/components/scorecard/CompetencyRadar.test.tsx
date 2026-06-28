import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";
import { CompetencyRadar } from "./CompetencyRadar";
import type { Scorecard } from "@/types/assay";

// recharts ResponsiveContainer relies on ResizeObserver, absent in jsdom.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === "undefined") {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    } as unknown as typeof ResizeObserver;
  }
});

function makeScorecard(overrides: Partial<Scorecard> = {}): Scorecard {
  return {
    run_id: "run_demo",
    status: "completed",
    certified: true,
    certificate_label: "Internal capability bar only",
    k: 3,
    thresholds: { competency: 0.8 },
    simulator_model: "assay-deterministic-sim-v1",
    pass_at_k: { compliance: true, fairness: false },
    competency_scores: { compliance: 0.96, fairness: 0.6 },
    seen_scores: { compliance: 0.96, fairness: 0.6 },
    held_out_scores: { compliance: 0.96, fairness: 0.6 },
    transfer_gap: { compliance: 0, fairness: 0.1 },
    grader_disagreement: 0.04,
    trace_audit: {
      status: "ok",
      tas_score: 88,
      grade: "Good",
      passes: true,
      total_steps: 8,
      total_tokens: 1200,
      metrics: {},
      savings: {},
      fixes: [],
      raw: {}
    },
    failure_reasons: [],
    created_at: "2026-06-27T00:00:00Z",
    lessons_applied: [],
    prior_run_id: null,
    ...overrides
  };
}

describe("CompetencyRadar", () => {
  it("shows the empty state instead of zero bars when there are no scores", () => {
    render(<CompetencyRadar competencyScores={{}} />);
    expect(screen.getByText(/run an evaluation to see competency scores/i)).toBeInTheDocument();
  });

  it("accepts a raw competency_scores map and lists each competency", () => {
    render(<CompetencyRadar competencyScores={{ compliance: 0.96 }} />);
    expect(screen.getAllByText("Compliance").length).toBeGreaterThan(0);
    expect(screen.getByText("96%")).toBeInTheDocument();
  });

  it("derives pass/fail from pass_at_k on a scorecard", () => {
    render(<CompetencyRadar scorecard={makeScorecard()} />);
    expect(screen.getByText("Pass")).toBeInTheDocument();
    expect(screen.getByText("Fail")).toBeInTheDocument();
    expect(screen.getByText("Certified")).toBeInTheDocument();
  });
});
