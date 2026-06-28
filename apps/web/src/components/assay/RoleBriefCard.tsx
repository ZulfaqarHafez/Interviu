"use client";

import * as React from "react";
import { Compass, ShieldAlert, ExternalLink } from "lucide-react";
import { assayApi } from "@/lib/api";
import type { RoleBrief } from "@/types/assay";

/**
 * What the judge was qualified with. Before grading, Assay researches what this
 * agent should be; this card surfaces that brief so the verdict reads as
 * grounded ("here is what we held it to") rather than a black box. It fetches
 * its own brief and renders nothing when the run produced none (stage off), so
 * it is safe to drop into any post-run view.
 */
export function RoleBriefCard({ runId }: { runId: string }) {
  const [brief, setBrief] = React.useState<RoleBrief | null>(null);

  React.useEffect(() => {
    let alive = true;
    assayApi
      .roleBrief(runId)
      .then((data) => {
        if (alive) setBrief(data);
      })
      .catch(() => {
        // 404 when the qualification stage was off — render nothing.
        if (alive) setBrief(null);
      });
    return () => {
      alive = false;
    };
  }, [runId]);

  if (!brief) return null;
  const offline = brief.mode === "deterministic";

  return (
    <section className="assay-rolebrief" aria-label="What the judge was qualified with">
      <h3 className="assay-section-label">
        <Compass size={15} aria-hidden="true" /> What we held it to
        {brief.mode === "deep" && <span className="assay-chip">deep research</span>}
        {offline && <span className="assay-chip muted">offline profile</span>}
      </h3>
      {brief.role_summary && <p className="assay-rolebrief-summary">{brief.role_summary}</p>}

      <div className="assay-rolebrief-cols">
        {brief.should_do.length > 0 && (
          <div>
            <h4>Should do</h4>
            <ul>{brief.should_do.slice(0, 5).map((line, i) => <li key={`do-${i}`}>{line}</li>)}</ul>
          </div>
        )}
        {brief.must_not_do.length > 0 && (
          <div>
            <h4><ShieldAlert size={13} aria-hidden="true" /> Must not</h4>
            <ul>{brief.must_not_do.slice(0, 5).map((line, i) => <li key={`no-${i}`}>{line}</li>)}</ul>
          </div>
        )}
      </div>

      {brief.competencies.length > 0 && (
        <div className="assay-rolebrief-comps">
          {brief.competencies.map((comp) => (
            <span key={comp.key} className={`assay-chip ${comp.difficulty}`} title={comp.why}>
              {comp.label}
            </span>
          ))}
        </div>
      )}

      {brief.sources.length > 0 && (
        <ul className="assay-rolebrief-sources">
          {brief.sources.slice(0, 5).map((src) => (
            <li key={src.url}>
              <a href={src.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink size={12} aria-hidden="true" /> {src.title || src.url}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default RoleBriefCard;
