import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import RunStateMachine from "./RunStateMachine";
import type { RunEvent } from "@/types/assay";

const gradedEvents: RunEvent[] = [
  {
    span_id: "g1",
    run_id: "run_1",
    sequence: 1,
    actor: "grader_panel",
    event_type: "response_graded",
    payload: { competency: "compliance", passed: true, score: 0.9 },
    started_at: "2026-06-27T00:00:00Z"
  },
  {
    span_id: "g2",
    run_id: "run_1",
    sequence: 2,
    actor: "grader_panel",
    event_type: "response_graded",
    payload: { competency: "fairness", passed: false, score: 0.4 },
    started_at: "2026-06-27T00:00:01Z"
  }
];

describe("RunStateMachine", () => {
  it("shows a determinate progressbar and graded cases while running", () => {
    render(
      <RunStateMachine
        status="running"
        progress={0.5}
        gradedCount={2}
        totalExpected={4}
        events={gradedEvents}
        onCancel={vi.fn()}
      />
    );
    const bar = screen.getByRole("progressbar", { name: /run progress/i });
    expect(bar).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("2 / 4 cases graded")).toBeInTheDocument();
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText("Fairness")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("enables Cancel only while the run is active", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <RunStateMachine
        status="running"
        progress={0.2}
        gradedCount={1}
        totalExpected={5}
        events={gradedEvents.slice(0, 1)}
        onCancel={onCancel}
      />
    );
    const cancel = screen.getByRole("button", { name: /cancel run/i });
    expect(cancel).toBeEnabled();
    await user.click(cancel);
    expect(onCancel).toHaveBeenCalledTimes(1);

    rerender(
      <RunStateMachine
        status="completed"
        progress={1}
        gradedCount={5}
        totalExpected={5}
        events={gradedEvents}
        onCancel={onCancel}
      />
    );
    expect(screen.getByRole("button", { name: /cancel run/i })).toBeDisabled();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("reports an indeterminate count when total is unknown", () => {
    render(
      <RunStateMachine
        status="running"
        progress={0}
        gradedCount={3}
        totalExpected={0}
        events={gradedEvents}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText("3 cases graded")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).not.toHaveAttribute("aria-valuenow");
  });
});
