import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SpanDetail from "./SpanDetail";
import type { RunEvent } from "@/types/assay";

function gradedSpan(overrides: Partial<RunEvent["payload"]> = {}): RunEvent {
  return {
    span_id: "span_grade",
    run_id: "run_1",
    sequence: 3,
    actor: "grader_panel",
    event_type: "response_graded",
    payload: {
      competency: "fairness",
      variant: "held_out",
      score: 0.42,
      passed: false,
      matched_checks: [],
      missed_checks: [{ label: "Counterfactual consistency" }],
      forbidden_hits: [{ label: "Used protected trait" }],
      feedback: "Protected trait influenced the decision.",
      ...overrides
    },
    started_at: "2026-06-27T00:00:00Z"
  };
}

describe("SpanDetail", () => {
  it("shows an empty hint when no span is selected", () => {
    render(<SpanDetail span={null} />);
    expect(screen.getByText(/select a span/i)).toBeInTheDocument();
  });

  it("surfaces the grader's reasoning for a failed response_graded span", () => {
    render(<SpanDetail span={gradedSpan()} />);
    expect(screen.getByText(/judge verdict/i)).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("0.42")).toBeInTheDocument();
    expect(screen.getByText("Protected trait influenced the decision.")).toBeInTheDocument();
    expect(screen.getByText("Counterfactual consistency")).toBeInTheDocument();
    expect(screen.getByText("Used protected trait")).toBeInTheDocument();
    expect(screen.getByText(/missed checks \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/forbidden hits \(1\)/i)).toBeInTheDocument();
  });

  it("marks a passing verdict", () => {
    render(<SpanDetail span={gradedSpan({ passed: true, score: 0.95, forbidden_hits: [] })} />);
    expect(screen.getByText("passed")).toBeInTheDocument();
    expect(screen.getByText("0.95")).toBeInTheDocument();
    expect(screen.queryByText(/forbidden hits/i)).not.toBeInTheDocument();
  });

  it("renders a key/value view (not raw JSON) for non-grading spans", () => {
    const span: RunEvent = {
      span_id: "span_ask",
      run_id: "run_1",
      sequence: 1,
      actor: "examiner",
      event_type: "question_asked",
      payload: { competency: "compliance", prompt: "Rank candidates.", difficulty: "standard" },
      started_at: "2026-06-27T00:00:00Z"
    };
    render(<SpanDetail span={span} />);
    expect(screen.queryByText(/judge verdict/i)).not.toBeInTheDocument();
    expect(screen.getByText("Prompt")).toBeInTheDocument();
    expect(screen.getByText("Rank candidates.")).toBeInTheDocument();
    expect(screen.getByText("Difficulty")).toBeInTheDocument();
  });
});
