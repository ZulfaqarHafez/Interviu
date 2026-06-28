import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import TraceDrawer from "./TraceDrawer";
import type { RunEvent, Scorecard, TracePayload } from "@/types/assay";

const events: RunEvent[] = [
  {
    span_id: "span_ask",
    run_id: "run_1",
    sequence: 1,
    actor: "examiner",
    event_type: "question_asked",
    payload: { competency: "compliance", prompt: "Rank candidates.", latency_ms: 12, tokens: 40 },
    started_at: "2026-06-27T00:00:00Z"
  },
  {
    span_id: "span_grade",
    run_id: "run_1",
    sequence: 2,
    actor: "grader_panel",
    event_type: "response_graded",
    payload: {
      competency: "compliance",
      score: 0.92,
      passed: true,
      matched_checks: [{ label: "Job related" }],
      missed_checks: [],
      forbidden_hits: [],
      feedback: "Stayed on job-related criteria.",
      latency_ms: 30,
      tokens: 88
    },
    started_at: "2026-06-27T00:00:01Z"
  }
];

const scorecard: Scorecard = {
  run_id: "run_1",
  status: "completed",
  certified: true,
  certificate_label: "Internal bar",
  k: 3,
  thresholds: { competency: 0.8 },
  simulator_model: "sim",
  pass_at_k: { compliance: true },
  competency_scores: { compliance: 0.92 },
  seen_scores: { compliance: 0.92 },
  held_out_scores: { compliance: 0.92 },
  transfer_gap: { compliance: 0.05 },
  grader_disagreement: 0,
  trace_audit: {
    status: "ok",
    trace_id: "t1",
    tas_score: 88,
    grade: "Good",
    passes: true,
    total_steps: 4,
    total_tokens: 100,
    metrics: {},
    savings: {},
    fixes: [],
    raw: {}
  },
  failure_reasons: [],
  created_at: "2026-06-27T00:00:00Z",
  lessons_applied: [],
  prior_run_id: null
};

const trace: TracePayload = { run_id: "run_1", events, scorecard };

function renderDrawer(open = true, onOpenChange = vi.fn()) {
  return render(
    <TraceDrawer
      events={events}
      trace={trace}
      scorecard={scorecard}
      proofBundle={null}
      agentSpec={null}
      agentResearch={null}
      open={open}
      onOpenChange={onOpenChange}
    />
  );
}

describe("TraceDrawer", () => {
  it("renders an accessible dialog with title and description when open", async () => {
    renderDrawer(true);
    const dialog = await screen.findByRole("dialog", { name: /trace inspector/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText(/run run_1/i)).toBeInTheDocument();
  });

  it("does not render when closed", () => {
    renderDrawer(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape (Radix focus-trap + key handling)", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    renderDrawer(true, onOpenChange);
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it("defaults the selection to the grading span and shows the judge verdict", async () => {
    renderDrawer(true);
    await screen.findByRole("dialog");
    // The judge verdict card surfaces the grader's reasoning.
    expect(await screen.findByText(/judge verdict/i)).toBeInTheDocument();
    expect(screen.getByText("Stayed on job-related criteria.")).toBeInTheDocument();
    expect(screen.getByText("Job related")).toBeInTheDocument();
  });

  it("toggles latency/token annotations in the span tree", async () => {
    const user = userEvent.setup();
    renderDrawer(true);
    await screen.findByRole("dialog");
    expect(screen.queryByText("12 ms · 40 tok")).not.toBeInTheDocument();
    await user.click(screen.getByLabelText(/latency & tokens/i));
    expect(await screen.findByText("12 ms · 40 tok")).toBeInTheDocument();
  });

  it("selecting a non-grading span shows a key/value payload view", async () => {
    const user = userEvent.setup();
    renderDrawer(true);
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("option", { name: /question asked/i }));
    // Payload key labelized; the grading verdict is no longer shown.
    expect(await screen.findByText("Prompt")).toBeInTheDocument();
    expect(screen.queryByText(/judge verdict/i)).not.toBeInTheDocument();
  });
});
