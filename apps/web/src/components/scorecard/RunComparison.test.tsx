import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RunComparison } from "./RunComparison";
import type { RunComparison as RunComparisonData } from "@/types/assay";

const useRunComparisonMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/queries", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/queries")>();
  return {
    ...actual,
    useRunComparison: (...args: Parameters<typeof actual.useRunComparison>) =>
      useRunComparisonMock(...args)
  };
});

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function makeComparison(overrides: Partial<RunComparisonData> = {}): RunComparisonData {
  return {
    schema: "assay.run_comparison.v1",
    run_id: "run_b",
    baseline_run_id: "run_a",
    candidate_id: "cand_demo",
    improved: 1,
    regressed: 1,
    unchanged: 0,
    certified_changed: false,
    competencies: [
      {
        competency: "compliance",
        label: "Compliance",
        baseline_score: 0.5,
        current_score: 0.9,
        delta: 0.4,
        outcome: "improved",
        baseline_passed: false,
        current_passed: true
      },
      {
        competency: "fairness",
        label: "Fairness",
        baseline_score: 0.9,
        current_score: 0.6,
        delta: -0.3,
        outcome: "regressed",
        baseline_passed: true,
        current_passed: false
      }
    ],
    ...overrides
  };
}

describe("RunComparison", () => {
  afterEach(() => {
    useRunComparisonMock.mockReset();
  });

  it("shows an empty state when there is no baseline run", () => {
    renderWithClient(
      <RunComparison
        runId="run_b"
        comparison={makeComparison({ baseline_run_id: null, competencies: [] })}
      />
    );
    expect(screen.getByText(/no prior run to compare against/i)).toBeInTheDocument();
  });

  it("renders one row per competency with baseline and current scores", () => {
    renderWithClient(<RunComparison runId="run_b" comparison={makeComparison()} />);
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Fairness")).toBeInTheDocument();
    // compliance: baseline 50% -> current 90%; fairness: baseline 90% -> current 60%
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getAllByText("90%").length).toBe(2);
  });

  it("renders signed, labelled deltas for improved and regressed competencies", () => {
    renderWithClient(<RunComparison runId="run_b" comparison={makeComparison()} />);
    expect(screen.getByText("+40%")).toBeInTheDocument();
    expect(screen.getByText("-30%")).toBeInTheDocument();
    expect(screen.getByLabelText(/improved, \+40%/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/regressed, -30%/i)).toBeInTheDocument();
  });

  it("notes when certification status changed", () => {
    renderWithClient(<RunComparison runId="run_b" comparison={makeComparison({ certified_changed: true })} />);
    expect(screen.getByText(/certification status changed/i)).toBeInTheDocument();
  });

  it("renders the shared workspace skeleton while loading", () => {
    useRunComparisonMock.mockReturnValue({ data: undefined, isLoading: true, error: null });
    const { container } = renderWithClient(<RunComparison runId="run_b" />);

    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument();
    expect(container.querySelector(".ws-skeleton-row")).toHaveStyle({ height: "72px" });
    expect(screen.queryByText(/loading comparison/i)).not.toBeInTheDocument();
  });
});
