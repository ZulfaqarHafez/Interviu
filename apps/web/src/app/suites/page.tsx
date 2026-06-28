"use client";

import * as React from "react";
import { Download, Upload } from "lucide-react";
import { assayApi } from "@/lib/api";
import { downloadJson, errorMessage } from "@/lib/derive";
import { useExamPacks, useImportExamPackFile } from "@/lib/queries";
import { ProbeArrayArt } from "@/components/ui/EmptyArt";

/**
 * Test suites — the adversarial datasets agents are run against. Each pack is a
 * versioned set of probes with seen + held-out variants and documented checks.
 */
export default function SuitesPage() {
  const packsQuery = useExamPacks();
  const importPack = useImportExamPackFile();
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const packs = packsQuery.data ?? [];

  async function handleImport(file: File | undefined) {
    if (!file) return;
    setMessage(null);
    try {
      const content = await file.text();
      const format = file.name.endsWith(".yml") ? "yml" : file.name.endsWith(".yaml") ? "yaml" : "json";
      const pack = await importPack.mutateAsync({ content, format });
      setMessage(`Imported ${pack.name}`);
    } catch (exc) {
      setMessage(errorMessage(exc));
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function exportPack(packId: string) {
    setMessage(null);
    try {
      const payload = await assayApi.examPackExport(packId);
      downloadJson(`${packId}-assay-exam-pack.json`, payload);
    } catch (exc) {
      setMessage(errorMessage(exc));
    }
  }

  return (
    <main className="ws-page">
      <header className="ws-head">
        <div>
          <h1>Test suites</h1>
          <p>Versioned datasets of adversarial probes with seen and held-out variants, graded against documented checks.</p>
        </div>
        <div className="ws-toolbar">
          <button
            type="button"
            className="ws-icon-button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="Import suite"
            title="Import suite"
            disabled={importPack.isPending}
          >
            <Upload size={15} />
          </button>
          <span className="ws-count">{packs.length} suite{packs.length === 1 ? "" : "s"}</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.yaml,.yml,application/json,text/yaml,text/x-yaml"
            hidden
            onChange={(event) => void handleImport(event.target.files?.[0])}
          />
        </div>
      </header>

      {message ? <p className="ws-surface-message" role="status">{message}</p> : null}

      {packsQuery.isLoading ? (
        <div className="ws-grid" aria-hidden="true">
          {Array.from({ length: 2 }).map((_, i) => (
            <div className="ws-skeleton-card" key={i} />
          ))}
        </div>
      ) : packs.length === 0 ? (
        <div className="ws-empty-rich">
          <ProbeArrayArt size={104} className="ws-empty-art" />
          <h2>No suites registered</h2>
          <p>Test suites are versioned datasets of adversarial probes. Once registered, each suite and its coverage shows up here.</p>
        </div>
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
                <div className="ws-card-actions">
                  <button
                    type="button"
                    className="ws-row-link as-button"
                    onClick={() => void exportPack(pack.id)}
                  >
                    <Download size={13} /> Export JSON
                  </button>
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
