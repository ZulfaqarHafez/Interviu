import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRunStream, type RunEventSource } from "./useRunStream";
import type { RunEvent, Scorecard } from "@/types/interviu";

const baseScorecard: Scorecard = {
  run_id: "run_1",
  status: "completed",
  certified: true,
  certificate_label: "Internal bar",
  k: 1,
  thresholds: {},
  simulator_model: "sim",
  pass_at_k: { compliance: true },
  competency_scores: { compliance: 1 },
  seen_scores: { compliance: 1 },
  held_out_scores: { compliance: 1 },
  transfer_gap: { compliance: 0 },
  grader_disagreement: 0,
  trace_audit: {
    status: "ok",
    passes: true,
    total_steps: 1,
    total_tokens: 10,
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

function gradedEvent(seq: number, competency: string): RunEvent {
  return {
    span_id: `span_${seq}`,
    run_id: "run_1",
    sequence: seq,
    actor: "grader_panel",
    event_type: "response_graded",
    payload: { competency, passed: true, score: 1 },
    started_at: "2026-06-27T00:00:00Z"
  };
}

/** A controllable event source so tests can push event snapshots on demand. */
function controllableSource() {
  let push: ((events: RunEvent[]) => void) | null = null;
  const source: RunEventSource = {
    subscribe(_runId, onEvents) {
      push = onEvents;
      return () => {
        push = null;
      };
    }
  };
  return {
    source,
    emit: (events: RunEvent[]) => act(() => push?.(events))
  };
}

let resolveStart: (value: Scorecard) => void;
let rejectStart: (reason: unknown) => void;

beforeEach(() => {
  global.fetch = vi.fn(
    (_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((resolve, reject) => {
        // Surface an abort the same way the browser fetch does.
        init?.signal?.addEventListener("abort", () => {
          const err = new DOMException("Aborted", "AbortError");
          reject(err);
        });
        resolveStart = (scorecard: Scorecard) =>
          resolve(
            new Response(JSON.stringify(scorecard), {
              status: 200,
              headers: { "Content-Type": "application/json" }
            })
          );
        rejectStart = reject;
      })
  ) as typeof fetch;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useRunStream", () => {
  it("starts in idle", () => {
    const { result } = renderHook(() => useRunStream());
    expect(result.current.status).toBe("idle");
    expect(result.current.progress).toBe(0);
  });

  it("transitions queued -> running -> completed with determinate progress", async () => {
    const { source, emit } = controllableSource();
    const { result } = renderHook(() => useRunStream(source));

    act(() => result.current.start("run_1", { k: 1, itemCount: 2 }));
    expect(result.current.status).toBe("queued");
    expect(result.current.totalExpected).toBe(2);

    emit([gradedEvent(1, "compliance")]);
    expect(result.current.status).toBe("running");
    expect(result.current.gradedCount).toBe(1);
    expect(result.current.progress).toBeCloseTo(0.5);

    emit([gradedEvent(1, "compliance"), gradedEvent(2, "fairness")]);
    expect(result.current.progress).toBeCloseTo(1);

    await act(async () => {
      resolveStart(baseScorecard);
      await Promise.resolve();
    });

    await waitFor(() => expect(result.current.status).toBe("completed"));
    expect(result.current.scorecard?.run_id).toBe("run_1");
    expect(result.current.isActive).toBe(false);
  });

  it("transitions to failed when the start request rejects", async () => {
    const { source } = controllableSource();
    const { result } = renderHook(() => useRunStream(source));
    act(() => result.current.start("run_1", { k: 1, itemCount: 1 }));

    await act(async () => {
      rejectStart(new Error("boom"));
      await Promise.resolve();
    });

    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.error).toMatch(/boom/);
  });

  it("cancel() aborts the in-flight start request and goes to canceled", async () => {
    const { source } = controllableSource();
    const { result } = renderHook(() => useRunStream(source));
    act(() => result.current.start("run_1", { k: 1, itemCount: 3 }));
    expect(result.current.status).toBe("queued");

    act(() => result.current.cancel());

    await waitFor(() => expect(result.current.status).toBe("canceled"));
    expect(result.current.isActive).toBe(false);
    // The start fetch was issued with an abort signal.
    const init = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]?.[1] as
      | RequestInit
      | undefined;
    expect(init?.signal).toBeDefined();
    expect(init?.signal?.aborted).toBe(true);
  });

  it("reset() returns to idle and clears state", async () => {
    const { source, emit } = controllableSource();
    const { result } = renderHook(() => useRunStream(source));
    act(() => result.current.start("run_1", { k: 1, itemCount: 1 }));
    emit([gradedEvent(1, "compliance")]);
    expect(result.current.gradedCount).toBe(1);

    act(() => result.current.reset());
    expect(result.current.status).toBe("idle");
    expect(result.current.gradedCount).toBe(0);
    expect(result.current.events).toHaveLength(0);
  });

  it("leaves progress at 0 when total is unknown (indeterminate)", () => {
    const { source, emit } = controllableSource();
    const { result } = renderHook(() => useRunStream(source));
    act(() => result.current.start("run_1"));
    emit([gradedEvent(1, "compliance")]);
    expect(result.current.totalExpected).toBe(0);
    expect(result.current.progress).toBe(0);
    expect(result.current.gradedCount).toBe(1);
  });
});
