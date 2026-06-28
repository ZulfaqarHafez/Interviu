"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, AlertTriangle, XCircle, ArrowRight, RotateCcw, PanelRightOpen, LayoutDashboard } from "lucide-react";
import { deriveVerdict, deriveFixes, deriveCategoryScores, type FixSeverity } from "@/lib/assay";
import RoleBriefCard from "@/components/assay/RoleBriefCard";
import type { Scorecard, AgentSpec } from "@/types/assay";

/**
 * The payoff screen. One verdict, one score, one biggest-problem sentence
 * (the 2-second glance), then the ranked "what to fix" list the developer came
 * for, then a category band that drills into evidence. Replaces the old wall of
 * nine always-open panels with a single progressive column.
 */

export type VerdictPanelProps = {
  scorecard: Scorecard;
  agentSpec: AgentSpec | null;
  agentName: string;
  onViewTrace: () => void;
  onTestAnother: () => void;
};

const VERDICT_ICON = {
  ship: CheckCircle2,
  risky: AlertTriangle,
  hold: XCircle
} as const;

const SEVERITY_LABEL: Record<FixSeverity, string> = {
  critical: "Critical",
  warn: "Warning",
  info: "Note"
};

export function VerdictPanel({ scorecard, agentSpec, agentName, onViewTrace, onTestAnother }: VerdictPanelProps) {
  const verdict = React.useMemo(() => deriveVerdict(scorecard), [scorecard]);
  const fixes = React.useMemo(() => deriveFixes(scorecard, agentSpec), [scorecard, agentSpec]);
  const categories = React.useMemo(() => deriveCategoryScores(scorecard), [scorecard]);
  const Icon = VERDICT_ICON[verdict.verdict];

  return (
    <section className="assay-verdict" aria-label="Verdict">
      {scorecard.degraded && (
        <div className="assay-demo-banner" role="status">
          <AlertTriangle size={16} />
          <span>
            <strong>Demo result.</strong> Your OpenAI key hit its rate limit (free tier is ~3 requests/min), so
            Assay graded with deterministic stand-in answers. Add billing to your OpenAI account for a live
            evaluation of your real agent.
          </span>
        </div>
      )}
      <div className={`assay-verdict-hero ${verdict.verdict}`}>
        <div className="assay-verdict-mark" aria-hidden="true">
          <Icon size={34} />
        </div>
        <div className="assay-verdict-copy">
          <span className="assay-verdict-eyebrow">{agentName}</span>
          <h2>{verdict.label}</h2>
          <p>{verdict.headline}</p>
        </div>
        <div className="assay-verdict-score" aria-label={`Capability score ${verdict.score} out of 100`}>
          <strong className="litmus-num">{verdict.score}</strong>
          <span>/ 100</span>
          <small>{verdict.passedChecks}/{verdict.totalChecks} checks held</small>
        </div>
      </div>

      <div className="assay-verdict-meter">
        <div
          className="assay-litmus-meter"
          role="img"
          aria-label={`Litmus score ${verdict.score} of 100 on the fail-to-ship scale`}
        >
          <span className="knob" style={{ left: `${Math.min(98, Math.max(2, verdict.score))}%` }} />
        </div>
        <div className="scale" aria-hidden="true">
          <span>Fail</span>
          <span>Risky</span>
          <span>Ship</span>
        </div>
      </div>

      <div className="assay-verdict-actions">
        <button type="button" className="assay-run-button slim" onClick={onTestAnother}>
          <RotateCcw size={16} /> Test another agent
        </button>
        <Link href={`/runs/${scorecard.run_id}`} className="assay-ghost-button">
          <LayoutDashboard size={16} /> Open in workspace
        </Link>
        <button type="button" className="assay-ghost-button" onClick={onViewTrace}>
          <PanelRightOpen size={16} /> Open full trace
        </button>
      </div>

      <RoleBriefCard runId={scorecard.run_id} />

      <div className="assay-fixes">
        <h3 className="assay-section-label">What to fix</h3>
        <ol className="assay-fix-list">
          {fixes.map((fix) => (
            <li key={fix.id} className={`assay-fix ${fix.severity}`}>
              <span className="assay-fix-sev">{SEVERITY_LABEL[fix.severity]}</span>
              <span className="assay-fix-body">
                <strong>{fix.title}</strong>
                <small>{fix.detail}</small>
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div className="assay-categories">
        <h3 className="assay-section-label">By capability</h3>
        <div className="assay-category-grid">
          {categories.map((category) => (
            <div key={category.competency} className={`assay-category ${category.passed ? "pass" : "fail"}`}>
              <span className="assay-category-name">{category.label}</span>
              <span className="assay-category-score">{category.score}%</span>
              <span className="assay-category-bar" aria-hidden="true">
                <span style={{ width: `${category.score}%` }} />
              </span>
            </div>
          ))}
          {categories.length === 0 && <p className="assay-muted">No competency breakdown for this run.</p>}
        </div>
      </div>

      <button type="button" className="assay-evidence-link" onClick={onViewTrace}>
        See the adversarial prompts and the judge&rsquo;s reasoning <ArrowRight size={14} />
      </button>
    </section>
  );
}

export default VerdictPanel;
