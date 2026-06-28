import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeAll, describe, expect, it } from "vitest";
import { ProgressTrend } from "./ProgressTrend";
import type { CandidateProgress } from "@/types/assay";

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

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function makeProgress(overrides: Partial<CandidateProgress> = {}): CandidateProgress {
  return {
    schema: "assay.candidate_progress.v1",
    candidate_id: "cand_demo",
    candidate_name: "Demo Candidate",
    run_count: 2,
    pass_rate: 0.5,
    competencies: [
      {
        competency: "compliance",
        label: "Compliance",
        first_score: 0.5,
        latest_score: 0.9,
        delta: 0.4,
        trend: "up",
        active_lessons: 1,
        points: [
          { run_id: "run_a", created_at: "2026-06-26T00:00:00Z", held_out_score: 0.5, passed: false, transfer_gap: 0.1, lessons_applied: 0 },
          { run_id: "run_b", created_at: "2026-06-27T00:00:00Z", held_out_score: 0.9, passed: true, transfer_gap: 0.05, lessons_applied: 1 }
        ]
      }
    ],
    runs: [],
    active_lessons: 1,
    ...overrides
  };
}

describe("ProgressTrend", () => {
  it("shows an empty state when there are fewer than two runs", () => {
    renderWithClient(<ProgressTrend candidateId="cand_demo" progress={makeProgress({ run_count: 1 })} />);
    expect(screen.getByText(/run this candidate at least twice/i)).toBeInTheDocument();
  });

  it("renders run count and pass rate stats with two or more runs", () => {
    renderWithClient(<ProgressTrend candidateId="cand_demo" progress={makeProgress()} />);
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Pass rate")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("exposes an accessible text summary of each competency trend", () => {
    renderWithClient(<ProgressTrend candidateId="cand_demo" progress={makeProgress()} />);
    expect(screen.getByText(/Compliance: from 50% to 90% \(up\)/i)).toBeInTheDocument();
  });
});
