"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  PanelRightOpen,
  Play,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  X
} from "lucide-react";
import { interviuApi } from "@/lib/api";
import type { CandidateConfig, Connector, ConnectorProbe, DatabaseHealth, ExamPack, ExamPackExport, ExamPackFileExport, ProofBundle, RunEvent, RunRecord, Scorecard, TracePayload } from "@/types/interviu";

type LoadState = "idle" | "loading" | "running" | "complete" | "error";

export default function Home() {
  const [health, setHealth] = useState<{ ok: boolean; tracerazor_importable: boolean; database_backend?: string } | null>(null);
  const [databaseHealth, setDatabaseHealth] = useState<DatabaseHealth | null>(null);
  const [examPacks, setExamPacks] = useState<ExamPack[]>([]);
  const [selectedExamPackId, setSelectedExamPackId] = useState("hr-v1");
  const [examPackExport, setExamPackExport] = useState<ExamPackExport | null>(null);
  const [examPackFileExport, setExamPackFileExport] = useState<ExamPackFileExport | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [connectorProbes, setConnectorProbes] = useState<ConnectorProbe[]>([]);
  const [recentRuns, setRecentRuns] = useState<RunRecord[]>([]);
  const [candidates, setCandidates] = useState<CandidateConfig[]>([]);
  const [candidate, setCandidate] = useState<CandidateConfig | null>(null);
  const [candidateName, setCandidateName] = useState("HTTP Candidate");
  const [candidateEndpoint, setCandidateEndpoint] = useState("");
  const [candidateModel, setCandidateModel] = useState("");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [trace, setTrace] = useState<TracePayload | null>(null);
  const [proofBundle, setProofBundle] = useState<ProofBundle | null>(null);
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [httpCandidateOpen, setHttpCandidateOpen] = useState(false);

  useEffect(() => {
    void loadBoot();
  }, []);

  const latestCompetency = useMemo(() => {
    const graded = [...events].reverse().find((event) => event.event_type === "response_graded");
    return String(graded?.payload.competency ?? "waiting");
  }, [events]);

  const passValues = Object.values(scorecard?.pass_at_k ?? {});
  const passedCount = passValues.filter(Boolean).length;
  const runLabel = scorecard?.certified ? "Passed" : scorecard ? "Needs review" : run?.status ?? "Ready";
  const spriteKind = state === "running"
    ? "candidate-review"
    : scorecard?.certified
      ? "candidate-approved"
      : scorecard
        ? "candidate-alert"
        : idleSpriteForPack(selectedExamPackId);
  const selectedExamPack = examPacks.find((pack) => pack.id === selectedExamPackId) ?? examPacks[0];
  const totalCount = passValues.length || (selectedExamPack?.items.length ?? 5);
  const probeById = useMemo(() => Object.fromEntries(connectorProbes.map((probe) => [probe.id, probe])), [connectorProbes]);
  const activationItems = useMemo(() => connectorProbes.filter((probe) => probe.status !== "pass").slice(0, 5), [connectorProbes]);
  const proofBundleHref = useMemo(
    () => (proofBundle ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(proofBundle, null, 2))}` : null),
    [proofBundle]
  );
  const proofBundleFilename = proofBundle ? `interviu-${proofBundle.run.id}-proof-bundle.json` : "interviu-proof-bundle.json";
  const examExportRows = examPackExport?.huggingface.files["data/interviu_exam_rows.jsonl"] ?? [];
  const examExportHref = examPackExport
    ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(examPackExport, null, 2))}`
    : null;
  const examExportFilename = examPackExport ? `interviu-${examPackExport.pack.id}-exam-pack.json` : "interviu-exam-pack.json";

  async function loadBoot() {
    setState("loading");
    setError(null);
    try {
      const [healthPayload, dbHealthPayload, packsPayload, connectorsPayload, probePayload, candidatesPayload, runsPayload] = await Promise.all([
        interviuApi.health(),
        interviuApi.databaseHealth(),
        interviuApi.examPacks(),
        interviuApi.connectors(),
        interviuApi.connectorProbes(),
        interviuApi.candidates(),
        interviuApi.runs()
      ]);
      setHealth(healthPayload);
      setDatabaseHealth(dbHealthPayload);
      setExamPacks(packsPayload);
      if (packsPayload.length && !packsPayload.some((pack) => pack.id === selectedExamPackId)) {
        setSelectedExamPackId(packsPayload[0].id);
      }
      setConnectors(connectorsPayload);
      setConnectorProbes(probePayload);
      setRecentRuns(runsPayload);
      setCandidates(candidatesPayload);
      setCandidate((currentCandidate) => {
        const stillAvailable = currentCandidate ? candidatesPayload.find((item) => item.id === currentCandidate.id) : null;
        return stillAvailable ?? candidatesPayload.find((item) => item.adapter_type === "mock") ?? candidatesPayload[0] ?? null;
      });
      setState("idle");
    } catch (exc) {
      setError(errorMessage(exc));
      setState("error");
    }
  }

  async function refreshConnectorProbes() {
    setError(null);
    try {
      const probePayload = await interviuApi.connectorProbes();
      setConnectorProbes(probePayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function prepareExamPackExport(packId = selectedExamPackId) {
    setError(null);
    try {
      const exportPayload = await interviuApi.examPackExport(packId);
      setExamPackExport(exportPayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function writeExamPackFiles(packId = selectedExamPackId) {
    setError(null);
    try {
      const exportPayload = await interviuApi.examPackFileExport(packId);
      setExamPackFileExport(exportPayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function registerHttpCandidate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const endpoint = candidateEndpoint.trim();
    if (!endpoint) {
      setError("Add an HTTP endpoint URL before registering a candidate.");
      return;
    }
    setError(null);
    try {
      const createdCandidate = await interviuApi.createCandidate({
          name: candidateName.trim() || "HTTP Candidate",
        adapter_type: "http",
        endpoint_url: endpoint,
        model: candidateModel.trim() || null,
        metadata: { source: "web-candidate-dock" }
      });
      setCandidates((currentCandidates) => [
        createdCandidate,
        ...currentCandidates.filter((item) => item.id !== createdCandidate.id)
      ]);
      setCandidate(createdCandidate);
      setCandidateEndpoint("");
      setHttpCandidateOpen(false);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  function useLocalStarterCandidate() {
    setCandidateName("Local Starter Candidate");
    setCandidateEndpoint("http://127.0.0.1:8080/ask");
    setCandidateModel("example-http-candidate");
    setError(null);
  }

  async function startDemoRun() {
    setState("running");
    setError(null);
    setEvents([]);
    setScorecard(null);
    setTrace(null);
    setProofBundle(null);
    try {
      const activeCandidate =
        candidate ??
        (await interviuApi.createCandidate({
          name: "Demo Candidate",
          adapter_type: "mock",
          metadata: { source: "web" }
        }));
      setCandidate(activeCandidate);
      const createdRun = await interviuApi.createRun(activeCandidate.id, selectedExamPack?.id ?? "hr-v1");
      setRun(createdRun);
      const result = await interviuApi.startRun(createdRun.id);
      setScorecard(result);
      setState("complete");
      const [eventPayload, tracePayload, bundlePayload, runsPayload] = await Promise.all([
        interviuApi.events(createdRun.id),
        interviuApi.trace(createdRun.id),
        interviuApi.proofBundle(createdRun.id),
        interviuApi.runs()
      ]);
      setEvents(eventPayload);
      setTrace(tracePayload);
      setProofBundle(bundlePayload);
      setRecentRuns(runsPayload);
      setState("complete");
    } catch (exc) {
      setError(errorMessage(exc));
      setState("error");
    }
  }

  async function loadPersistedRun(runId: string) {
    setState("loading");
    setError(null);
    try {
      const [tracePayload, bundlePayload] = await Promise.all([
        interviuApi.trace(runId),
        interviuApi.proofBundle(runId)
      ]);
      setRun(bundlePayload.run);
      setCandidate(bundlePayload.candidate);
      if (bundlePayload.candidate) {
        setCandidates((currentCandidates) => [
          bundlePayload.candidate as CandidateConfig,
          ...currentCandidates.filter((item) => item.id !== bundlePayload.candidate?.id)
        ]);
      }
      setScorecard(bundlePayload.scorecard);
      setEvents(tracePayload.events);
      setTrace(tracePayload);
      setProofBundle(bundlePayload);
      setDrawerOpen(true);
      setState("complete");
    } catch (exc) {
      setError(errorMessage(exc));
      setState("error");
    }
  }

  async function exportProofBundle() {
    const runId = run?.id ?? scorecard?.run_id;
    if (!runId) {
      setError("Run an evaluation first, then export the proof bundle.");
      return;
    }
    setError(null);
    try {
      const bundlePayload = await interviuApi.proofBundle(runId);
      setProofBundle(bundlePayload);
      downloadJson(`interviu-${runId}-proof-bundle.json`, bundlePayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  return (
    <main className="app-shell">
      <section className="arena-band" aria-label="Interviu evaluation room">
        <div className="topbar">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true" />
            <div>
              <h1>Interviu</h1>
              <p>Local evaluation workspace</p>
            </div>
          </div>
          <div className="toolbar">
            <button className="icon-button" type="button" title="Refresh" onClick={loadBoot}>
              <RefreshCw size={18} />
            </button>
            <button className="icon-button" type="button" title="Probe connectors" onClick={refreshConnectorProbes}>
              <Activity size={18} />
            </button>
            <button className="icon-button" type="button" title="Open trace drawer" onClick={() => setDrawerOpen(true)}>
              <PanelRightOpen size={18} />
            </button>
            <button className="icon-button" type="button" title="Export proof bundle" onClick={exportProofBundle}>
              <Save size={18} />
            </button>
            <button className="command-button primary" type="button" onClick={startDemoRun} disabled={state === "running" || state === "loading"}>
              <Play size={18} />
              Run evaluation
            </button>
          </div>
        </div>

        <div className="arena">
          <div className="room-panel">
            <div className="room-copy">
              <span className="eyebrow">{state === "running" ? "Running" : "Ready"}</span>
              <h2>{candidate?.name ?? "Demo Candidate"}</h2>
              <p>{selectedExamPack?.name ?? "HR screening reliability"}</p>
            </div>
            <div className="candidate-zone">
              <div className={`sprite-sheet hero-sprite sprite-${spriteKind} ${state === "running" ? "thinking" : ""}`} aria-hidden="true" />
            </div>
            <div className="room-summary">
              <div>
                <span>Outcome</span>
                <strong>{runLabel}</strong>
              </div>
              <div>
                <span>Current focus</span>
                <strong>{labelize(latestCompetency)}</strong>
              </div>
              <div className="badges" aria-label="pass at k progress">
                {Array.from({ length: totalCount }).map((_, index) => {
                  const isKnown = index < passValues.length;
                  const passed = passValues[index];
                  return (
                    <span className={`badge ${isKnown ? (passed ? "pass" : "fail") : ""}`} key={index}>
                      {isKnown ? (passed ? "P" : "F") : index + 1}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        <div className="status-strip">
          <Metric label="Run" value={run?.id ?? "Not started"} />
          <Metric label="Checks" value={`${passedCount}/${totalCount}`} />
          <Metric label="Trace audit" value={traceStatus(scorecard)} />
          <Metric label="Storage" value={health?.database_backend ?? "sqlite"} />
        </div>
      </section>

      <aside className="side-panel" aria-label="evaluation controls">
        <section className="panel-section setup-section">
          <h2 className="section-title">Run setup</h2>
          <div className="candidate-dock-card">
            <span className={`sprite-sheet mini-sprite ${candidateDockSprite(candidate)}`} aria-hidden="true" />
            <span>
              <strong>{candidate?.name ?? "No candidate selected"}</strong>
              <small>{candidate?.adapter_type ?? "mock"}{candidate?.endpoint_url ? ` / ${candidate.endpoint_url}` : ""}</small>
            </span>
            <span className={`pill ${candidate?.adapter_type === "http" ? "connected" : "ready"}`}>
              {candidate?.adapter_type ?? "none"}
            </span>
          </div>
          <label className="field-row">
            <span>Candidate</span>
            <select
              value={candidate?.id ?? ""}
              onChange={(event) => {
                setCandidate(candidates.find((item) => item.id === event.target.value) ?? null);
              }}
            >
              {candidates.length ? (
                candidates.map((item) => (
                  <option value={item.id} key={item.id}>{item.name} / {item.adapter_type}</option>
                ))
              ) : (
                <option value="">No candidates loaded</option>
              )}
            </select>
          </label>
          <label className="field-row">
            <span>Exam pack</span>
            <select
              value={selectedExamPackId}
              onChange={(event) => {
                setSelectedExamPackId(event.target.value);
                setExamPackExport(null);
                setExamPackFileExport(null);
              }}
            >
              {examPacks.map((pack) => (
                <option value={pack.id} key={pack.id}>{pack.name}</option>
              ))}
            </select>
          </label>
          <details
            className="setup-details"
            open={httpCandidateOpen}
            onToggle={(event) => setHttpCandidateOpen(event.currentTarget.open)}
          >
            <summary>
              <Plus size={16} />
              Add HTTP candidate
            </summary>
            <div className="candidate-form-tools">
              <button className="command-button" type="button" onClick={useLocalStarterCandidate}>
                <Activity size={16} />
                Use local starter
              </button>
            </div>
            <form className="candidate-form" onSubmit={registerHttpCandidate}>
              <label className="field-row">
                <span>Name</span>
                <input
                  value={candidateName}
                  onChange={(event) => setCandidateName(event.target.value)}
                  placeholder="HTTP Candidate"
                />
              </label>
              <label className="field-row">
                <span>Endpoint</span>
                <input
                  value={candidateEndpoint}
                  onChange={(event) => setCandidateEndpoint(event.target.value)}
                  placeholder="http://127.0.0.1:8080/ask"
                  inputMode="url"
                />
              </label>
              <label className="field-row">
                <span>Model tag</span>
                <input
                  value={candidateModel}
                  onChange={(event) => setCandidateModel(event.target.value)}
                  placeholder="optional"
                />
              </label>
              <button className="command-button" type="submit">
                <Plus size={16} />
                Add HTTP
              </button>
            </form>
          </details>
        </section>

        <section className="panel-section">
          <h2 className="section-title">Score</h2>
          <div className={`score-hero ${scorecard?.certified ? "passed" : scorecard ? "review" : ""}`}>
            <span>{scorecard?.certified ? "Passed" : scorecard ? "Needs review" : "Not run yet"}</span>
            {scorecard?.certified ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          </div>
          {Object.entries(scorecard?.competency_scores ?? emptyCompetencies(selectedExamPack)).slice(0, 5).map(([name, value]) => (
            <div className="bar-row" key={name}>
              <span>{labelize(name)}</span>
              <div className="bar-track" aria-label={`${name} score`}>
                <div className="bar-fill" style={{ width: `${Math.round(value * 100)}%` }} />
              </div>
              <strong>{Math.round(value * 100)}</strong>
            </div>
          ))}
        </section>

        <section className="panel-section">
          <h2 className="section-title">Proof</h2>
          <div className="connector-row">
            <span>Trace score</span>
            <strong>{traceScoreLabel(scorecard)}</strong>
          </div>
          <div className="connector-row">
            <span>Status</span>
            <strong>{traceAuditStatus(scorecard, health?.tracerazor_importable)}</strong>
          </div>
          <div className="connector-row">
            <span>Transfer gap</span>
            <strong>{scorecard ? maxTransferGap(scorecard).toFixed(2) : "0.00"}</strong>
          </div>
          <div className="library-actions">
            <button className="command-button" type="button" onClick={() => setDrawerOpen(true)}>
              <PanelRightOpen size={16} />
              View trace
            </button>
            <button className="command-button" type="button" onClick={exportProofBundle}>
              <Save size={16} />
              Export proof
            </button>
          </div>
        </section>

        <details className="panel-section quiet-details">
          <summary>Exam export</summary>
          <div className="connector-row">
            <span>{selectedExamPack?.id ?? "no-pack"}</span>
            <strong>{selectedExamPack?.items.length ?? 0} items</strong>
          </div>
          <div className="connector-row">
            <span>Dataset rows</span>
            <strong>{examExportRows.length || ((selectedExamPack?.items.length ?? 0) * 2)}</strong>
          </div>
          <div className="library-actions">
            <button className="command-button" type="button" onClick={() => prepareExamPackExport()}>
              <Save size={16} />
              Prepare export
            </button>
            <button className="command-button" type="button" onClick={() => writeExamPackFiles()}>
              <Save size={16} />
              Write files
            </button>
            {examExportHref && (
              <a className="command-button" href={examExportHref} download={examExportFilename}>
                <Save size={16} />
                Save pack
              </a>
            )}
          </div>
          {examPackFileExport && (
            <div className="artifact-card">
              <span>Local export</span>
              <strong>{examPackFileExport.row_count} rows</strong>
              <small>{examPackFileExport.directory}</small>
            </div>
          )}
        </details>

        <details className="panel-section quiet-details">
          <summary>Recent runs</summary>
          {recentRuns.length ? (
            recentRuns.slice(0, 5).map((item) => (
              <button className="ledger-row" type="button" key={item.id} onClick={() => loadPersistedRun(item.id)}>
                <span>
                  <strong>{item.id}</strong>
                  <small>{item.status} / {item.exam_pack_id}</small>
                </span>
                <span>{item.k}x</span>
              </button>
            ))
          ) : (
            <div className="connector-row">No stored runs yet</div>
          )}
          {proofBundle && (
            <div className="proof-summary">
              <span>Bundle</span>
              <strong>{proofBundle.summary.event_count} spans / {proofBundle.summary.trace_status}</strong>
            </div>
          )}
        </details>

        <details className="panel-section quiet-details">
          <summary>System details</summary>
          {activationItems.length ? (
            activationItems.map((item) => (
              <div className="activation-row" key={item.id}>
                <span className={`probe-dot ${item.status}`} aria-hidden="true" />
                <span>
                  <strong>{item.name}</strong>
                  <small>{item.next_step ?? item.evidence}</small>
                </span>
                <em>{item.status}</em>
              </div>
            ))
          ) : (
            <div className="connector-row">All connector checks pass</div>
          )}
          {connectors.map((connector) => {
            const probe = probeById[connector.id] ?? (connector.id === "supabase" ? probeById.supabase : null);
            return (
              <div className="connector-card" key={connector.id}>
                <div className="connector-card-main">
                  <span className="connector-copy">
                    <span className={`sprite-sheet mini-sprite ${connectorIcon(connector.id)}`} aria-hidden="true" />
                    <span>
                      <strong>{connector.name}</strong>
                      <small>{connector.description}</small>
                    </span>
                  </span>
                  <span className={`pill ${connector.status}`}>{connector.status}</span>
                </div>
                {probe && (
                  <div className="probe-line">
                    <span className={`probe-dot ${probe.status}`} aria-hidden="true" />
                    <span>{probe.evidence}</span>
                    <strong>{probe.status}</strong>
                  </div>
                )}
              </div>
            );
          })}
        </details>

        {(scorecard?.failure_reasons.length || error) ? (
          <section className="panel-section">
            <h2 className="section-title">Needs attention</h2>
            {scorecard?.failure_reasons.map((failure) => (
              <div className="failure-row" key={failure}>{failure}</div>
            ))}
            {error && <p className="error-text">{error}</p>}
          </section>
        ) : null}
      </aside>

      {drawerOpen && (
        <TraceDrawer
          events={events}
          trace={trace}
          scorecard={scorecard}
          proofBundle={proofBundle}
          proofBundleHref={proofBundleHref}
          proofBundleFilename={proofBundleFilename}
          databaseHealth={databaseHealth}
          onExport={exportProofBundle}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TraceDrawer({
  events,
  trace,
  scorecard,
  proofBundle,
  proofBundleHref,
  proofBundleFilename,
  databaseHealth,
  onExport,
  onClose
}: {
  events: RunEvent[];
  trace: TracePayload | null;
  scorecard: Scorecard | null;
  proofBundle: ProofBundle | null;
  proofBundleHref: string | null;
  proofBundleFilename: string;
  databaseHealth: DatabaseHealth | null;
  onExport: () => void;
  onClose: () => void;
}) {
  const audit = scorecard?.trace_audit;
  return (
    <aside className="drawer" aria-label="trace drawer">
      <div className="drawer-header">
        <div>
          <h2 className="section-title">Trace</h2>
          <strong>{trace?.run_id ?? "No run selected"}</strong>
        </div>
        <div className="drawer-actions">
          {proofBundleHref ? (
            <a className="icon-button" title="Download proof bundle" href={proofBundleHref} download={proofBundleFilename}>
              <Save size={18} />
            </a>
          ) : (
            <button className="icon-button" type="button" title="Export proof bundle" onClick={onExport}>
              <Save size={18} />
            </button>
          )}
          <button className="icon-button" type="button" title="Close trace drawer" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
      </div>
      <div className="connector-row">
        <span><Activity size={16} /> TraceRazor {audit?.status ?? "pending"}</span>
        <strong>{audit?.grade ?? "no grade"}</strong>
      </div>
      <div className="connector-row">
        <span><ShieldCheck size={16} /> transfer_gap</span>
        <strong>{scorecard ? maxTransferGap(scorecard).toFixed(2) : "0.00"}</strong>
      </div>
      <div className="connector-row">
        <span>Database health</span>
        <strong>{databaseHealth?.backend ?? "unknown"} / {databaseHealth?.ok ? "ok" : "pending"}</strong>
      </div>
      <div className="connector-row">
        <span>Proof bundle</span>
        <strong>{proofBundle ? `${proofBundle.summary.event_count} spans` : "not exported"}</strong>
      </div>
      {(events.length ? events : trace?.events ?? []).map((event) => (
        <article className="event-row" key={event.span_id}>
          <header>
            <span>{event.sequence}. {event.actor} / {event.event_type}</span>
            <span>{event.tracerazor_step_id ? `TR ${event.tracerazor_step_id}` : "span"}</span>
          </header>
          <pre>{JSON.stringify(event.payload, null, 2)}</pre>
        </article>
      ))}
    </aside>
  );
}

function emptyCompetencies(pack?: ExamPack): Record<string, number> {
  const names = pack?.items.map((item) => item.competency) ?? [
    "compliance",
    "fairness",
    "ambiguity_handling",
    "refusal_boundaries",
    "interview_ethics"
  ];
  return Object.fromEntries(Array.from(new Set(names)).map((name) => [name, 0]));
}

function idleSpriteForPack(packId: string) {
  return packId.includes("injection") ? "candidate-proof" : "candidate-ready";
}

function labelize(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function traceStatus(scorecard: Scorecard | null) {
  if (!scorecard) {
    return "pending";
  }
  const audit = scorecard.trace_audit;
  return audit.tas_score === null || audit.tas_score === undefined
    ? audit.status
    : `${audit.tas_score.toFixed(0)} ${audit.grade ?? ""}`.trim();
}

function traceScoreLabel(scorecard: Scorecard | null) {
  const audit = scorecard?.trace_audit;
  if (!audit) return "Pending";
  if (audit.tas_score !== null && audit.tas_score !== undefined) return audit.tas_score.toFixed(1);
  if (audit.status === "error" || audit.status === "unavailable") return "Not scored";
  if (audit.status === "insufficient_steps") return "Insufficient";
  return "Pending";
}

function traceAuditStatus(scorecard: Scorecard | null, traceRazorImportable?: boolean) {
  const status = scorecard?.trace_audit.status;
  if (status) return labelize(status);
  return traceRazorImportable ? "Ready" : "Unavailable";
}

function maxTransferGap(scorecard: Scorecard) {
  return Math.max(0, ...Object.values(scorecard.transfer_gap));
}

function connectorIcon(id: string) {
  if (id.includes("supabase")) return "sprite-supabase";
  if (id.includes("hugging")) return "sprite-hugging-face";
  if (id.includes("vercel")) return "sprite-vercel";
  if (id.includes("trace")) return "sprite-tracerazor";
  if (id.includes("http")) return "sprite-http-antenna";
  if (id.includes("mcp")) return "sprite-mcp-plug";
  if (id.includes("openai")) return "sprite-model-chip";
  if (id.includes("local")) return "sprite-local-command";
  return "sprite-candidate";
}

function candidateDockSprite(candidate: CandidateConfig | null) {
  if (candidate?.adapter_type === "http") return "sprite-http-antenna";
  if (candidate?.adapter_type === "mcp-server") return "sprite-mcp-plug";
  if (candidate?.adapter_type === "local-command") return "sprite-local-command";
  if (candidate?.adapter_type === "openai-compatible") return "sprite-model-chip";
  return "sprite-candidate";
}

function downloadJson(filename: string, payload: unknown) {
  if (typeof window === "undefined") {
    return;
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function errorMessage(exc: unknown) {
  return exc instanceof Error ? exc.message : "Unknown Interviu error";
}
