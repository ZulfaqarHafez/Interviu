"use client";

import * as React from "react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Sprite } from "@/components/ui/Sprite";
import { useCandidateLessons } from "@/lib/queries";
import { errorMessage, labelize } from "@/lib/derive";
import type { DiagnosticLesson, LessonOutcome } from "@/types/assay";

/** Maps a lesson outcome to a Badge variant + human label. */
const OUTCOME_META: Record<LessonOutcome, { variant: "pass" | "fail" | "warn" | "neutral"; label: string }> = {
  improved: { variant: "pass", label: "Improved" },
  regressed: { variant: "fail", label: "Regressed" },
  still_failing: { variant: "warn", label: "Still failing" },
  unchanged: { variant: "neutral", label: "Unchanged" },
  pending: { variant: "neutral", label: "Pending" }
};

function shortRunId(runId: string) {
  return runId.length > 12 ? `${runId.slice(0, 8)}…` : runId;
}

export type DiagnosticLibraryProps = {
  /** Candidate whose persisted lessons should be listed. */
  candidateId: string | null | undefined;
  /** Optional exam-pack filter forwarded to the API. */
  examPackId?: string;
  /** Optional pre-fetched lessons. When provided the hook is skipped. */
  lessons?: DiagnosticLesson[];
  className?: string;
};

/**
 * The visible "diagnostic library": every lesson the loop has persisted for a
 * candidate, grouped by competency, with origin run, how many runs re-applied
 * it, an outcome badge, and an active/retired chip.
 */
export function DiagnosticLibrary({ candidateId, examPackId, lessons: provided, className }: DiagnosticLibraryProps) {
  const query = useCandidateLessons(provided ? null : candidateId, examPackId);
  const lessons = provided ?? query.data;
  const isLoading = !provided && query.isLoading;
  const error = !provided ? query.error : null;

  const header = (
    <CardHeader>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <Sprite name="lesson-book" sheet="lessons" aria-hidden="true" />
        <span style={{ fontWeight: 700 }}>Diagnostic library</span>
      </span>
      {lessons && lessons.length > 0 ? (
        <Badge variant="neutral" aria-label={`${lessons.length} lessons`}>
          {lessons.length} lesson{lessons.length === 1 ? "" : "s"}
        </Badge>
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
            Could not load lessons: {errorMessage(error)}
          </p>
        </CardBody>
      </Card>
    );
  }

  if (!lessons || lessons.length === 0) {
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
            <Sprite name="library-empty" sheet="lessons" scale={2} aria-hidden="true" />
            <p style={{ color: "var(--color-fg-muted)", fontSize: 13, margin: 0, maxWidth: 320 }}>
              No lessons yet. When a competency falls short, the loop records a lesson here and re-applies it on the
              next run.
            </p>
          </div>
        </CardBody>
      </Card>
    );
  }

  // Group lessons by competency, preserving first-seen order.
  const groups: Array<{ competency: string; label: string; items: DiagnosticLesson[] }> = [];
  for (const lesson of lessons) {
    let group = groups.find((candidate) => candidate.competency === lesson.competency);
    if (!group) {
      group = { competency: lesson.competency, label: labelize(lesson.competency), items: [] };
      groups.push(group);
    }
    group.items.push(lesson);
  }

  return (
    <Card className={className}>
      {header}
      <CardBody>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {groups.map((group) => (
            <section key={group.competency} aria-label={`${group.label} lessons`}>
              <h4
                style={{
                  margin: "0 0 8px",
                  fontSize: 12,
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                  color: "var(--color-fg-muted)"
                }}
              >
                {group.label}
              </h4>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 10 }}>
                {group.items.map((lesson) => (
                  <LessonRow key={lesson.id} lesson={lesson} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function LessonRow({ lesson }: { lesson: DiagnosticLesson }) {
  const outcome = OUTCOME_META[lesson.latest_outcome] ?? OUTCOME_META.pending;
  const appliedCount = lesson.applied_run_ids.length;
  return (
    <li
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        background: "var(--color-soft)",
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 8
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-fg)", lineHeight: 1.4 }}>{lesson.text}</p>
        <span style={{ display: "inline-flex", gap: 6, flexShrink: 0 }}>
          <Badge variant={outcome.variant}>{outcome.label}</Badge>
          <Badge variant={lesson.active ? "ready" : "planned"}>{lesson.active ? "Active" : "Retired"}</Badge>
        </span>
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          fontSize: 11,
          color: "var(--color-fg-muted)"
        }}
      >
        <span>
          Origin{" "}
          <code style={{ color: "var(--color-fg)" }} title={lesson.origin_run_id}>
            {shortRunId(lesson.origin_run_id)}
          </code>{" "}
          ({Math.round(lesson.origin_score * 100)}%)
        </span>
        <span>
          Applied in {appliedCount} run{appliedCount === 1 ? "" : "s"}
        </span>
        {lesson.latest_outcome_score !== null && lesson.latest_outcome_score !== undefined ? (
          <span>Latest {Math.round(lesson.latest_outcome_score * 100)}%</span>
        ) : null}
      </div>
    </li>
  );
}

export default DiagnosticLibrary;
