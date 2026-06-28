"use client";

import * as React from "react";
import { Check, X, Loader2 } from "lucide-react";
import { liveSteps, roleQualified, tailoredExam, type LiveStep } from "@/lib/assay";
import BrandMark from "@/components/ui/BrandMark";
import type { RunEvent } from "@/types/assay";
import type { RunStreamStatus } from "@/lib/useRunStream";

/**
 * The "show the work" surface: an adversarial exam, animated as a live
 * chain-of-thought waterfall. Each probe enters with a slide+fade, the active
 * probe pulses, and it resolves to a held-up / broke verdict. The wait is the
 * product demo — Perplexity found users tolerate longer waits when the steps
 * are visible and labeled. Honors prefers-reduced-motion via CSS.
 */

export type JudgingWaterfallProps = {
  status: RunStreamStatus;
  events: RunEvent[];
  gradedCount: number;
  totalExpected: number;
  progress: number;
  agentName: string;
  onCancel: () => void;
};

export function JudgingWaterfall({
  status,
  events,
  gradedCount,
  totalExpected,
  progress,
  agentName,
  onCancel
}: JudgingWaterfallProps) {
  const steps = React.useMemo(() => liveSteps(events), [events]);
  const qualify = React.useMemo(() => roleQualified(events), [events]);
  const tailored = React.useMemo(() => tailoredExam(events), [events]);
  const grades = steps.filter((step) => step.kind === "grade");
  const isActive = status === "queued" || status === "running";
  const determinate = totalExpected > 0;
  const pct = Math.round((determinate ? progress : isActive ? 0.05 : 1) * 100);

  // The most recent probe still awaiting a grade is the "active" one.
  const lastGradedSeq = grades.length ? grades[grades.length - 1].sequence : 0;
  const active = isActive ? steps.find((step) => step.kind === "ask" && step.sequence > lastGradedSeq) : undefined;

  const visible: LiveStep[] = React.useMemo(() => {
    const rows = grades.slice();
    if (active) rows.push(active);
    // Newest first reads better for a live feed.
    return rows.sort((a, b) => b.sequence - a.sequence).slice(0, 12);
  }, [grades, active]);

  const heading =
    status === "queued"
      ? `Warming up the examiner…`
      : status === "running"
        ? `Stress-testing ${agentName}`
        : status === "failed"
          ? `The run hit an error`
          : status === "canceled"
            ? `Run canceled`
            : `Tallying the verdict…`;

  return (
    <section className="assay-judging" aria-label="Live judging">
      <header className="assay-judging-head">
        <span className="assay-judging-title">
          <span className={`assay-flask ${isActive ? "bubbling" : ""}`} aria-hidden="true">
            <BrandMark size={36} />
          </span>
          <strong>{heading}</strong>
        </span>
        <div className="assay-judging-meta">
          <span className="assay-judging-count" aria-live="polite">
            {determinate ? `${gradedCount} / ${totalExpected} probes` : `${gradedCount} probes`}
          </span>
          {isActive && (
            <button type="button" className="assay-cancel" onClick={onCancel}>
              Cancel
            </button>
          )}
        </div>
      </header>

      <div
        className="assay-progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label="Exam progress"
      >
        <div
          className={`assay-progress-fill ${status === "failed" ? "fail" : status === "completed" ? "done" : ""}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <ul className="assay-waterfall" aria-live="polite">
        {qualify && (
          <li className="assay-step pass assay-step-qualify">
            <span className="assay-step-icon" aria-hidden="true">
              <Check size={15} />
            </span>
            <span className="assay-step-body">
              <strong>
                Judge qualified{qualify.mode === "deep" ? " · deep research" : qualify.mode === "deterministic" ? " · offline profile" : " · researched the role"}
              </strong>
              {qualify.summary && <small>{qualify.summary}</small>}
              {qualify.sourceCount > 0 && <small>{qualify.sourceCount} source{qualify.sourceCount === 1 ? "" : "s"} cited</small>}
            </span>
          </li>
        )}
        {tailored && (
          <li className="assay-step pass assay-step-qualify">
            <span className="assay-step-icon" aria-hidden="true">
              <Check size={15} />
            </span>
            <span className="assay-step-body">
              <strong>Built {tailored.itemCount} tailored probe{tailored.itemCount === 1 ? "" : "s"}</strong>
              {tailored.competencies.length > 0 && <small>{tailored.competencies.join(" · ")}</small>}
            </span>
          </li>
        )}
        {visible.length === 0 && (
          <li className="assay-step pending">
            <span className="assay-step-icon spin" aria-hidden="true">
              <Loader2 size={15} />
            </span>
            <span className="assay-step-body">
              <strong>Loading the adversarial exam…</strong>
              <small>The examiner is preparing its first probe.</small>
            </span>
          </li>
        )}
        {visible.map((step) => (
          <li key={`${step.id}-${step.kind}`} className={`assay-step ${step.status}`}>
            <span className="assay-step-icon" aria-hidden="true">
              {step.status === "pass" ? (
                <Check size={15} />
              ) : step.status === "fail" ? (
                <X size={15} />
              ) : (
                <Loader2 size={15} className="assay-spin" />
              )}
            </span>
            <span className="assay-step-body">
              <strong>{step.label}</strong>
              {step.detail && <small>{step.detail}</small>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default JudgingWaterfall;
