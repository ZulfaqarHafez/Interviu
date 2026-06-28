import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { DiagnosticLibrary } from "./DiagnosticLibrary";
import type { DiagnosticLesson } from "@/types/assay";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function makeLesson(overrides: Partial<DiagnosticLesson> = {}): DiagnosticLesson {
  return {
    id: "lesson_1",
    candidate_id: "cand_demo",
    exam_pack_id: "hr-v1",
    competency: "compliance",
    text: "Keep protected traits out of ranking decisions.",
    origin_run_id: "run_origin_aaaa",
    origin_score: 0.5,
    origin_variant: "held_out",
    created_at: "2026-06-26T00:00:00Z",
    updated_at: "2026-06-27T00:00:00Z",
    applied_run_ids: ["run_b"],
    last_applied_at: "2026-06-27T00:00:00Z",
    latest_outcome: "improved",
    latest_outcome_score: 0.9,
    active: true,
    ...overrides
  };
}

describe("DiagnosticLibrary", () => {
  it("shows an empty state when there are no lessons", () => {
    renderWithClient(<DiagnosticLibrary candidateId="cand_demo" lessons={[]} />);
    expect(screen.getByText(/no lessons yet/i)).toBeInTheDocument();
  });

  it("groups lessons by competency and shows origin + applied count", () => {
    renderWithClient(<DiagnosticLibrary candidateId="cand_demo" lessons={[makeLesson()]} />);
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(screen.getByText(/keep protected traits out of ranking/i)).toBeInTheDocument();
    expect(screen.getByText(/applied in 1 run/i)).toBeInTheDocument();
  });

  it("renders an improved outcome badge and an active chip", () => {
    renderWithClient(<DiagnosticLibrary candidateId="cand_demo" lessons={[makeLesson()]} />);
    expect(screen.getByText("Improved")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders a regressed badge and a retired chip when applicable", () => {
    renderWithClient(
      <DiagnosticLibrary
        candidateId="cand_demo"
        lessons={[makeLesson({ id: "lesson_2", latest_outcome: "regressed", active: false })]}
      />
    );
    expect(screen.getByText("Regressed")).toBeInTheDocument();
    expect(screen.getByText("Retired")).toBeInTheDocument();
  });
});
