"use client";

import * as React from "react";
import { useExamPacks } from "@/lib/queries";

/**
 * Test suites — the adversarial datasets agents are run against. Each pack is a
 * versioned set of probes with seen + held-out variants and documented checks.
 */
export default function SuitesPage() {
  const packsQuery = useExamPacks();
  const packs = packsQuery.data ?? [];

  return (
    <main className="ws-page">
      <header className="ws-head">
        <div>
          <h1>Test suites</h1>
          <p>Versioned datasets of adversarial probes with seen and held-out variants, graded against documented checks.</p>
        </div>
        <span className="ws-count">{packs.length} suite{packs.length === 1 ? "" : "s"}</span>
      </header>

      {packsQuery.isLoading ? (
        <div className="ws-empty">Loading suites…</div>
      ) : packs.length === 0 ? (
        <div className="ws-empty">No suites registered.</div>
      ) : (
        <div className="ws-grid">
          {packs.map((pack) => {
            const competencies = Array.from(new Set(pack.items.map((i) => i.competency)));
            return (
              <article className="ws-card" key={pack.id}>
                <h2 className="ws-card-title">{pack.name}</h2>
                <p className="ws-card-sub mono">{pack.id}</p>
                <div className="ws-card-meta">
                  <span className="ws-chip accent">{pack.items.length} probes</span>
                  <span className="ws-chip">{competencies.length} competencies</span>
                  <span className="ws-chip">seen + held-out</span>
                </div>
                <div className="ws-card-meta">
                  {competencies.slice(0, 6).map((c) => (
                    <span className="ws-chip" key={c}>{labelize(c)}</span>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </main>
  );
}

function labelize(key: string) {
  return key.replace(/[_-]+/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}
