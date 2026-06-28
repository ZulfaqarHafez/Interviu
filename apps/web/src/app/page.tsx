"use client";

import React from "react";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  PanelRightOpen,
  Play,
  Plus,
  RefreshCw,
  Save,
  Sparkles
} from "lucide-react";
import { interviuApi } from "@/lib/api";
import {
  useCandidates,
  useConnectorProbes,
  useConnectors,
  useDatabaseHealth,
  useExamPacks,
  useHealth,
  useRuns
} from "@/lib/queries";
import { useRunStream } from "@/lib/useRunStream";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  buildReviewers,
  buildRoster,
  buildWorkflow,
  candidateDockSprite,
  connectorIcon,
  errorMessage,
  idleSpriteForPack,
  labelize,
  maxTransferGap,
  readinessLabel,
  readinessSprite,
  refineryHeroClass,
  runSprite,
  traceAuditStatus,
  traceScoreLabel,
  traceStatus,
  type LoadState
} from "@/lib/derive";
import TraceDrawer from "@/components/trace/TraceDrawer";
import CompetencyRadar from "@/components/scorecard/CompetencyRadar";
import RunStateMachine from "@/components/run/RunStateMachine";
import EmptyState from "@/components/onboarding/EmptyState";
import AgentIntake from "@/components/assay/AgentIntake";
import Landing from "@/components/assay/Landing";
import JudgingWaterfall from "@/components/assay/JudgingWaterfall";
import VerdictPanel from "@/components/assay/VerdictPanel";
import { AGENT_TEMPLATES } from "@/lib/assayTemplates";
import ProgressTrend from "@/components/progress/ProgressTrend";
import DiagnosticLibrary from "@/components/library/DiagnosticLibrary";
import RunComparison from "@/components/scorecard/RunComparison";
import type {
  AgentResearch,
  AgentSpec,
  CandidateConfig,
  ExamPackExport,
  ExamPackFileExport,
  JobScope,
  ProductReview,
  ProofBundle,
  RoleAnalysis,
  RunEvent,
  RunRecord,
  Scorecard,
  TracePayload
} from "@/types/interviu";

export default function Home() {
  // Boot data via TanStack Query (cache, retry, dedupe handled by the client).
  const healthQuery = useHealth();
  const databaseHealthQuery = useDatabaseHealth();
  const examPacksQuery = useExamPacks();
  const connectorsQuery = useConnectors();
  const connectorProbesQuery = useConnectorProbes();
  const candidatesQuery = useCandidates();
  const runsQuery = useRuns();

  const health = healthQuery.data ?? null;
  const databaseHealth = databaseHealthQuery.data ?? null;
  const examPacks = useMemo(() => examPacksQuery.data ?? [], [examPacksQuery.data]);
  const connectors = useMemo(() => connectorsQuery.data ?? [], [connectorsQuery.data]);
  const connectorProbes = useMemo(() => connectorProbesQuery.data ?? [], [connectorProbesQuery.data]);
  const candidates = useMemo(() => candidatesQuery.data ?? [], [candidatesQuery.data]);
  const recentRuns = useMemo(() => runsQuery.data ?? [], [runsQuery.data]);

  const bootLoading =
    healthQuery.isLoading ||
    examPacksQuery.isLoading ||
    candidatesQuery.isLoading ||
    runsQuery.isLoading;

  // Run-scoped state set imperatively once a run resolves.
  const [selectedExamPackId, setSelectedExamPackId] = useState("hr-v1");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [examPackExport, setExamPackExport] = useState<ExamPackExport | null>(null);
  const [examPackFileExport, setExamPackFileExport] = useState<ExamPackFileExport | null>(null);
  const [extraCandidates, setExtraCandidates] = useState<CandidateConfig[]>([]);
  const [candidateName, setCandidateName] = useState("HTTP Candidate");
  const [candidateEndpoint, setCandidateEndpoint] = useState("");
  const [candidateModel, setCandidateModel] = useState("");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [trace, setTrace] = useState<TracePayload | null>(null);
  const [proofBundle, setProofBundle] = useState<ProofBundle | null>(null);
  const [productReview, setProductReview] = useState<ProductReview | null>(null);
  const [agentSpec, setAgentSpec] = useState<AgentSpec | null>(null);
  const [agentExport, setAgentExport] = useState<{ run_id: string; directory: string; sub_agent_count: number } | null>(null);
  const [agentResearch, setAgentResearch] = useState<AgentResearch | null>(null);
  const [researchBusy, setResearchBusy] = useState<"fast" | "deep" | null>(null);
  const [jobScopeText, setJobScopeText] = useState("");
  const [roleAnalysis, setRoleAnalysis] = useState<RoleAnalysis | null>(null);
  const [roleBusy, setRoleBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [httpCandidateOpen, setHttpCandidateOpen] = useState(false);
  const [intakeSubmitting, setIntakeSubmitting] = useState(false);

  const runStream = useRunStream();

  // Merge server candidates with any registered locally this session.
  const allCandidates = useMemo(() => {
    const seen = new Set<string>();
    const merged: CandidateConfig[] = [];
    for (const item of [...extraCandidates, ...candidates]) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      merged.push(item);
    }
    return merged;
  }, [extraCandidates, candidates]);

  const candidate = useMemo(() => {
    if (selectedCandidateId) {
      const match = allCandidates.find((item) => item.id === selectedCandidateId);
      if (match) return match;
    }
    return allCandidates.find((item) => item.adapter_type === "mock") ?? allCandidates[0] ?? null;
  }, [selectedCandidateId, allCandidates]);

  // Map run-stream lifecycle onto the legacy LoadState the derive helpers expect.
  const state: LoadState = useMemo(() => {
    if (runStream.status === "queued" || runStream.status === "running") return "running";
    if (error || runStream.status === "failed") return "error";
    if (scorecard) return "complete";
    if (bootLoading) return "loading";
    return "idle";
  }, [runStream.status, error, scorecard, bootLoading]);

  const isRunning = state === "running";

  // When the stream completes, capture the scorecard and load the run artifacts.
  useEffect(() => {
    if (runStream.status !== "completed" || !runStream.scorecard) return;
    const completedScorecard = runStream.scorecard;
    setScorecard(completedScorecard);
    void hydrateRunArtifacts(completedScorecard.run_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runStream.status, runStream.scorecard]);

  // Surface stream failures in the existing error channel.
  useEffect(() => {
    if (runStream.status === "failed" && runStream.error) {
      setError(runStream.error);
    }
  }, [runStream.status, runStream.error]);

  // Keep the live events in sync with the stream while running.
  useEffect(() => {
    if (isRunning && runStream.events.length) {
      setEvents(runStream.events);
    }
  }, [isRunning, runStream.events]);

  // Default the selected pack to a valid one once packs load.
  useEffect(() => {
    if (examPacks.length && !examPacks.some((pack) => pack.id === selectedExamPackId)) {
      setSelectedExamPackId(examPacks[0].id);
    }
  }, [examPacks, selectedExamPackId]);

  const latestCompetency = useMemo(() => {
    const graded = [...events].reverse().find((event) => event.event_type === "response_graded");
    return String(graded?.payload.competency ?? "waiting");
  }, [events]);

  const passValues = Object.values(scorecard?.pass_at_k ?? {});
  const passedCount = passValues.filter(Boolean).length;
  const runLabel = scorecard?.certified ? "Passed" : scorecard ? "Needs review" : run?.status ?? "Ready";
  const spriteKind = isRunning
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
  const examExportRows = examPackExport?.huggingface.files["data/interviu_exam_rows.jsonl"] ?? [];
  const examExportHref = examPackExport
    ? `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(examPackExport, null, 2))}`
    : null;
  const examExportFilename = examPackExport ? `interviu-${examPackExport.pack.id}-exam-pack.json` : "interviu-exam-pack.json";
  const rosterCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const event of events) {
      counts[event.actor] = (counts[event.actor] ?? 0) + 1;
    }
    return counts;
  }, [events]);
  const roster = useMemo(
    () => buildRoster(isRunning, rosterCounts, scorecard, selectedExamPack?.simulator_model),
    [isRunning, rosterCounts, scorecard, selectedExamPack?.simulator_model]
  );
  const workflow = useMemo(
    () => buildWorkflow(state, scorecard, agentSpec, roleAnalysis, passedCount, totalCount),
    [state, scorecard, agentSpec, roleAnalysis, passedCount, totalCount]
  );
  const reviewers = useMemo(
    () => productReview?.reviewers ?? buildReviewers(state, scorecard, health, databaseHealth, proofBundle),
    [productReview, state, scorecard, health, databaseHealth, proofBundle]
  );
  const agentMarkdownHref = useMemo(
    () => (agentSpec ? `data:text/markdown;charset=utf-8,${encodeURIComponent(agentSpec.agent_markdown)}` : null),
    [agentSpec]
  );
  const agentMarkdownFilename = agentSpec ? `interviu-${agentSpec.run_id}-AGENTS.md` : "AGENTS.md";

  const hasAnyData = allCandidates.length > 0 || recentRuns.length > 0 || run !== null;
  const showEmptyState = !bootLoading && !hasAnyData && !isRunning;

  function refreshBoot() {
    setError(null);
    void healthQuery.refetch();
    void databaseHealthQuery.refetch();
    void examPacksQuery.refetch();
    void connectorsQuery.refetch();
    void connectorProbesQuery.refetch();
    void candidatesQuery.refetch();
    void runsQuery.refetch();
  }

  function refreshConnectorProbes() {
    setError(null);
    void connectorProbesQuery.refetch();
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
      setExtraCandidates((current) => [createdCandidate, ...current.filter((item) => item.id !== createdCandidate.id)]);
      setSelectedCandidateId(createdCandidate.id);
      void candidatesQuery.refetch();
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

  function resetRunArtifacts() {
    setEvents([]);
    setScorecard(null);
    setTrace(null);
    setProofBundle(null);
    setProductReview(null);
    setAgentSpec(null);
    setAgentExport(null);
    setAgentResearch(null);
  }

  async function hydrateRunArtifacts(runId: string) {
    try {
      const [eventPayload, tracePayload, bundlePayload, reviewPayload] = await Promise.all([
        interviuApi.events(runId),
        interviuApi.trace(runId),
        interviuApi.proofBundle(runId),
        interviuApi.reviewers(runId)
      ]);
      setEvents(eventPayload);
      setTrace(tracePayload);
      setProofBundle(bundlePayload);
      setProductReview(reviewPayload);
      setAgentSpec(bundlePayload.agent_spec ?? null);
      setRoleAnalysis(bundlePayload.role_analysis ?? null);
      void runsQuery.refetch();
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function startDemoRun() {
    setError(null);
    resetRunArtifacts();
    runStream.reset();
    try {
      let activeCandidate = candidate;
      if (!activeCandidate) {
        activeCandidate = await interviuApi.createCandidate({
          name: "Demo Candidate",
          adapter_type: "mock",
          metadata: { source: "web" }
        });
        setExtraCandidates((current) => [activeCandidate as CandidateConfig, ...current]);
        setSelectedCandidateId(activeCandidate.id);
        void candidatesQuery.refetch();
      }
      const jobScope = jobScopeText.trim() ? buildJobScope(jobScopeText.trim()) : null;
      const createdRun = await interviuApi.createRun(
        activeCandidate.id,
        selectedExamPack?.id ?? selectedExamPackId ?? "hr-v1",
        jobScope
      );
      setRun(createdRun);
      runStream.start(createdRun.id, { k: createdRun.k, itemCount: selectedExamPack?.items.length });
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  function cancelRun() {
    runStream.cancel();
  }

  // Assay primary flow: take an uploaded/authored agent.md, register it as the
  // candidate under test (live LLM when a key is set, deterministic demo when
  // not), then immediately run the adversarial exam and stream the judging.
  async function runAgentMarkdown(markdown: string) {
    if (!markdown.trim()) return;
    setError(null);
    resetRunArtifacts();
    runStream.reset();
    setRun(null);
    setIntakeSubmitting(true);
    try {
      const intake = await interviuApi.candidateFromMarkdown(markdown);
      const created = intake.candidate;
      setExtraCandidates((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setSelectedCandidateId(created.id);
      void candidatesQuery.refetch();
      const packId = selectedExamPack?.id ?? selectedExamPackId ?? "hr-v1";
      const createdRun = await interviuApi.createRun(created.id, packId, null);
      setRun(createdRun);
      runStream.start(createdRun.id, { k: createdRun.k, itemCount: selectedExamPack?.items.length });
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setIntakeSubmitting(false);
    }
  }

  // Return to the calm intake screen to test another agent.
  function testAnother() {
    setError(null);
    resetRunArtifacts();
    runStream.reset();
    setRun(null);
  }

  async function loadPersistedRun(runId: string) {
    setError(null);
    runStream.reset();
    try {
      const [tracePayload, bundlePayload, reviewPayload] = await Promise.all([
        interviuApi.trace(runId),
        interviuApi.proofBundle(runId),
        interviuApi.reviewers(runId)
      ]);
      setRun(bundlePayload.run);
      if (bundlePayload.candidate) {
        const loadedCandidate = bundlePayload.candidate;
        setExtraCandidates((current) => [loadedCandidate, ...current.filter((item) => item.id !== loadedCandidate.id)]);
        setSelectedCandidateId(loadedCandidate.id);
      }
      setScorecard(bundlePayload.scorecard);
      setEvents(tracePayload.events);
      setTrace(tracePayload);
      setProofBundle(bundlePayload);
      setProductReview(reviewPayload);
      setAgentSpec(bundlePayload.agent_spec ?? null);
      setRoleAnalysis(bundlePayload.role_analysis ?? null);
      setAgentExport(null);
      setAgentResearch(null);
      setDrawerOpen(true);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function openTraceDrawer() {
    const runId = scorecard?.run_id ?? run?.id;
    if (!runId) {
      setDrawerOpen(true);
      return;
    }
    const hasCurrentTrace = trace?.run_id === runId;
    const hasCurrentBundle = proofBundle?.run.id === runId;
    if (!hasCurrentTrace || !hasCurrentBundle) {
      setError(null);
      try {
        const [tracePayload, bundlePayload, reviewPayload] = await Promise.all([
          interviuApi.trace(runId),
          interviuApi.proofBundle(runId),
          interviuApi.reviewers(runId)
        ]);
        setEvents(tracePayload.events);
        setTrace(tracePayload);
        setProofBundle(bundlePayload);
        setProductReview(reviewPayload);
        setAgentSpec(bundlePayload.agent_spec ?? null);
        setRoleAnalysis(bundlePayload.role_analysis ?? null);
      } catch (exc) {
        setError(errorMessage(exc));
      }
    }
    setDrawerOpen(true);
  }

  async function refreshAgentSpec() {
    const runId = scorecard?.run_id ?? run?.id;
    if (!runId) {
      setError("Run an evaluation first, then refine the agent spec.");
      return;
    }
    setError(null);
    try {
      const spec = await interviuApi.agentSpec(runId);
      setAgentSpec(spec);
      setDrawerOpen(true);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function writeAgentSpecFiles() {
    const runId = agentSpec?.run_id ?? scorecard?.run_id ?? run?.id;
    if (!runId) {
      setError("Run an evaluation first, then export the agent spec.");
      return;
    }
    setError(null);
    try {
      const exportPayload = await interviuApi.agentSpecFileExport(runId);
      setAgentExport(exportPayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  async function runResearch(mode: "fast" | "deep") {
    const runId = agentSpec?.run_id ?? scorecard?.run_id ?? run?.id;
    if (!runId) {
      setError("Run an evaluation first, then research the agent with OpenAI.");
      return;
    }
    setError(null);
    setResearchBusy(mode);
    try {
      const research = await interviuApi.agentResearch(runId, mode);
      setAgentResearch(research);
      setDrawerOpen(true);
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setResearchBusy(null);
    }
  }

  async function analyzeRole() {
    setError(null);
    setRoleBusy(true);
    try {
      const analysis = await interviuApi.roleAnalysis(jobScopeText.trim());
      setRoleAnalysis(analysis);
      if (analysis.recommended_exam_pack_id && examPacks.some((pack) => pack.id === analysis.recommended_exam_pack_id)) {
        setSelectedExamPackId(analysis.recommended_exam_pack_id);
      }
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setRoleBusy(false);
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
      setProductReview(bundlePayload.product_review ?? null);
      downloadJson(`interviu-${runId}-proof-bundle.json`, bundlePayload);
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  const comparisonBaseline = scorecard?.prior_run_id ?? run?.id ?? null;
  const activeRunId = scorecard?.run_id ?? run?.id ?? null;

  // Phase drives the calm, single-focus primary surface: intake → judging → verdict.
  const runEnded = runStream.status === "failed" || runStream.status === "canceled";
  const phase: "intake" | "running" | "verdict" = scorecard
    ? "verdict"
    : isRunning || runEnded
      ? "running"
      : "intake";

  return (
    <main className="assay-shell">
      <div className="assay-stage">
        {phase === "intake" && (
          <>
            <AgentIntake
              examPackName={selectedExamPack?.name ?? "the exam"}
              liveMode={Boolean(health?.openai_configured)}
              submitting={intakeSubmitting}
              templates={AGENT_TEMPLATES}
              onRun={runAgentMarkdown}
            />
            <Landing
              onStart={() => {
                const el = document.querySelector<HTMLTextAreaElement>(".assay-textarea");
                el?.scrollIntoView({ behavior: "smooth", block: "center" });
                el?.focus();
              }}
            />
          </>
        )}
        {phase === "running" && (
          <JudgingWaterfall
            status={runStream.status}
            events={runStream.events}
            gradedCount={runStream.gradedCount}
            totalExpected={runStream.totalExpected}
            progress={runStream.progress}
            agentName={candidate?.name ?? "your agent"}
            onCancel={cancelRun}
          />
        )}
        {phase === "verdict" && scorecard && (
          <VerdictPanel
            scorecard={scorecard}
            agentSpec={agentSpec}
            agentName={candidate?.name ?? scorecard.run_id}
            onViewTrace={openTraceDrawer}
            onTestAnother={testAnother}
          />
        )}
        {error && phase !== "verdict" && (
          <p className="assay-error" role="alert">{error}</p>
        )}
        {runEnded && (
          <div className="assay-retry">
            <button type="button" className="assay-ghost-button" onClick={testAnother}>
              Back to start
            </button>
          </div>
        )}
      </div>

      <details className="assay-advanced">
        <summary>Evaluation cockpit (advanced)</summary>
        <div className="app-shell">
      <section className="arena-band workbench" aria-label="Interviu evaluation workspace">
        <div className="topbar">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <div>
              <h1>Assay cockpit</h1>
              <p>Trace-backed evaluation workspace</p>
            </div>
          </div>
          <div className="toolbar">
            <ThemeToggle />
            <button className="icon-button" type="button" title="Refresh" onClick={refreshBoot}>
              <RefreshCw size={18} />
            </button>
            <button className="icon-button" type="button" title="Probe connectors" onClick={refreshConnectorProbes}>
              <Activity size={18} />
            </button>
            <button className="icon-button" type="button" title="Open trace drawer" onClick={openTraceDrawer}>
              <PanelRightOpen size={18} />
            </button>
            <button className="icon-button" type="button" title="Export proof bundle" onClick={exportProofBundle}>
              <Save size={18} />
            </button>
            <button className="command-button primary" type="button" onClick={startDemoRun} disabled={isRunning || bootLoading}>
              <Play size={18} />
              Run evaluation
            </button>
          </div>
        </div>

        {showEmptyState ? (
          <section className="panel-section" aria-label="get started" style={{ borderBottom: "none" }}>
            <EmptyState
              examPackId={selectedExamPackId}
              onRunComplete={(completedRun, completedScorecard) => {
                setRun(completedRun);
                setSelectedCandidateId(completedRun.candidate_id);
                setScorecard(completedScorecard);
                void candidatesQuery.refetch();
                void hydrateRunArtifacts(completedRun.id);
              }}
            />
          </section>
        ) : null}

        <div className="cockpit-grid">
          <section className="run-brief" aria-label="current evaluation">
            <div className="run-brief-copy">
              <span className={`eyebrow ${isRunning ? "live" : ""}`}>{isRunning ? "Running" : runLabel}</span>
              <h2>{candidate?.name ?? "Demo Candidate"}</h2>
              <p>{selectedExamPack?.name ?? "HR screening reliability"}</p>
              <div className="brief-tags" aria-label="evaluation context">
                <span>{selectedExamPack?.items.length ?? 5} checks</span>
                <span>pass^{scorecard?.k ?? run?.k ?? 3}</span>
                <span>{scorecard?.simulator_model ?? selectedExamPack?.simulator_model ?? "deterministic simulator"}</span>
              </div>
            </div>
            <div className="candidate-zone compact">
              <div className={`sprite-sheet hero-sprite sprite-${spriteKind} ${isRunning ? "thinking" : ""}`} aria-hidden="true" />
            </div>
          </section>

          <section className="metric-deck" aria-label="run summary">
            <MetricTile label="Outcome" value={runLabel} tone={scorecard?.certified ? "pass" : scorecard ? "warn" : "neutral"} />
            <MetricTile label="Trace score" value={traceScoreLabel(scorecard)} tone={scorecard?.trace_audit.passes ? "pass" : scorecard ? "warn" : "neutral"} />
            <MetricTile label="Transfer gap" value={scorecard ? maxTransferGap(scorecard).toFixed(2) : "0.00"} tone={scorecard && maxTransferGap(scorecard) <= (scorecard.thresholds.max_transfer_gap ?? 0.2) ? "pass" : "neutral"} />
            <MetricTile label="Storage" value={health?.database_backend ?? "sqlite"} tone={databaseHealth?.ok === false ? "warn" : "neutral"} />
          </section>

          <section className="evidence-panel" aria-label="evaluation evidence">
            <div className="panel-head">
              <span className="roster-title">
                <Bot size={16} /> Evaluation panel {isRunning ? "working" : scorecard ? "complete" : "ready"}
              </span>
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
            <div className="workflow-strip" aria-label="evaluation workflow">
              {workflow.map((item) => (
                <div className={`workflow-card ${item.state}`} key={item.key}>
                  <span className={`sprite-sheet ${item.sheet} workflow-sprite sprite-${item.sprite}`} aria-hidden="true" />
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.meta}</small>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="focus-panel" aria-label="current focus">
            <span>Current focus</span>
            <strong>{labelize(latestCompetency)}</strong>
            <small>{run?.id ?? "No run started"}</small>
            <div className="focus-facts">
              <div>
                <span>Gate</span>
                <strong>{passedCount}/{totalCount}</strong>
              </div>
              <div>
                <span>Threshold</span>
                <strong>{Math.round((scorecard?.thresholds.competency ?? 0.8) * 100)}%</strong>
              </div>
              <div>
                <span>Judge variance</span>
                <strong>{scorecard ? scorecard.grader_disagreement.toFixed(2) : "0.00"}</strong>
              </div>
            </div>
          </section>

          <section className="agent-roster evidence-panel" aria-label="interview agent panel">
            <div className="roster-track">
              {roster.map((agent) => (
                <div className={`roster-agent ${agent.state}`} key={agent.key} title={agent.title}>
                  <span
                    className={`sprite-sheet ${agent.sheet} roster-sprite sprite-${agent.sprite} ${agent.state === "active" ? "thinking" : ""}`}
                    aria-hidden="true"
                  />
                  <span className="roster-name">{agent.label}</span>
                  <span className="roster-meta">{agent.meta}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        {(isRunning || runStream.status === "failed" || runStream.status === "canceled") && (
          <section className="panel-section" aria-label="run progress" style={{ borderBottom: "none" }}>
            <RunStateMachine
              status={runStream.status}
              progress={runStream.progress}
              gradedCount={runStream.gradedCount}
              totalExpected={runStream.totalExpected}
              events={runStream.events}
              onCancel={cancelRun}
            />
          </section>
        )}

        {activeRunId || candidate ? (
          <section className="learning-surfaces" aria-label="learning surfaces">
            <CompetencyRadar scorecard={scorecard} />
            <RunComparison runId={activeRunId} baseline={comparisonBaseline ?? undefined} />
            <ProgressTrend candidateId={candidate?.id ?? null} />
            <DiagnosticLibrary candidateId={candidate?.id ?? null} examPackId={selectedExamPackId} />
          </section>
        ) : null}

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
              onChange={(event) => setSelectedCandidateId(event.target.value || null)}
            >
              {allCandidates.length ? (
                allCandidates.map((item) => (
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
          <label className="field-row">
            <span>Job scope</span>
            <textarea
              className="job-scope-input"
              value={jobScopeText}
              onChange={(event) => setJobScopeText(event.target.value)}
              placeholder="Paste a role or job scope, for example: Screen and rank candidates fairly; parse resume uploads; handle SSNs and medical notes."
              rows={3}
            />
          </label>
          <button className="command-button" type="button" onClick={analyzeRole} disabled={roleBusy || !jobScopeText.trim()}>
            <Sparkles size={16} />
            {roleBusy ? "Analyzing..." : "Analyze role"}
          </button>
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
          <h2 className="section-title">Decision logic</h2>
          {roleAnalysis ? (
            <>
              <p className="refinery-headline">
                Role needs <strong>{roleAnalysis.requirements.length}</strong> competenc{roleAnalysis.requirements.length === 1 ? "y" : "ies"} /
                pack <strong>{roleAnalysis.recommended_exam_pack_id}</strong>
                {roleAnalysis.supplemental_pack_ids.length ? ` (+${roleAnalysis.supplemental_pack_ids.join(", ")})` : ""} /{" "}
                <span className="pill ready">{roleAnalysis.extraction_status}</span>
              </p>
              {roleAnalysis.requirements.map((req) => (
                <div className="decision-row" key={req.competency}>
                  <div className="decision-head">
                    <strong>{labelize(req.competency)}</strong>
                    <span className={`pill ${req.priority === "recommended" ? "ready" : "planned"}`}>
                      {req.priority === "recommended" ? "required" : "optional"}
                    </span>
                    {!req.covered_by_pack && <span className="pill warn">not tested</span>}
                  </div>
                  <p>{req.rationale}</p>
                  {req.sources.length > 0 && (
                    <div className="decision-sources">
                      {req.sources.slice(0, 3).map((source, index) => (
                        <em key={`${index}-${source.phrase}`}>&ldquo;{source.phrase}&rdquo;</em>
                      ))}
                    </div>
                  )}
                  <small className="decision-meta">
                    {req.expected_check_ids.length} check{req.expected_check_ids.length === 1 ? "" : "s"}
                    {req.recommended_subagent_id ? ` / ${req.recommended_subagent_id}` : ""}
                  </small>
                </div>
              ))}
              {roleAnalysis.compliance_notes.length > 0 && (
                <div className="failure-row">
                  <strong>Compliance guard:</strong>
                  <ul className="decision-compliance">
                    {roleAnalysis.compliance_notes.map((note, index) => (
                      <li key={`${index}-${note}`}>{note}</li>
                    ))}
                  </ul>
                </div>
              )}
              {roleAnalysis.uncovered_competencies.length > 0 && (
                <p className="refinery-note">Not yet tested: {roleAnalysis.uncovered_competencies.join(", ")}</p>
              )}
            </>
          ) : (
            <p className="refinery-note">
              Add a job scope above and click &ldquo;Analyze role&rdquo; to see which competencies, checks, and helpers the role needs, with reasons.
            </p>
          )}
        </section>

        <section className="panel-section">
          <h2 className="section-title">Score</h2>
          <div className={`score-hero ${scorecard?.certified ? "passed" : scorecard ? "review" : ""}`}>
            <span>{scorecard?.certified ? "Passed" : scorecard ? "Needs review" : "Not run yet"}</span>
            {scorecard?.certified ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          </div>
          <CompetencyRadar scorecard={scorecard} />
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
            <button className="command-button" type="button" onClick={openTraceDrawer}>
              <PanelRightOpen size={16} />
              View trace
            </button>
            <button className="command-button" type="button" onClick={exportProofBundle}>
              <Save size={16} />
              Export proof
            </button>
          </div>
        </section>

        <section className="panel-section">
          <h2 className="section-title">Reviewers</h2>
          <div className="reviewer-list">
            {reviewers.map((reviewer) => (
              <div className={`reviewer-row ${reviewer.status}`} key={reviewer.key}>
                <span className={`sprite-sheet mini-sprite sprite-${reviewer.sprite}`} aria-hidden="true" />
                <span>
                  <strong>{reviewer.name}</strong>
                  <small>{reviewer.summary}</small>
                </span>
                <span className={`pill ${reviewer.status === "pass" ? "ready" : reviewer.status === "warn" ? "warn" : "planned"}`}>
                  {reviewer.label}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel-section">
          <h2 className="section-title">Coaching plan</h2>
          {agentSpec ? (
            <>
              <div className={`score-hero ${refineryHeroClass(agentSpec.readiness)}`}>
                <span className="refinery-verdict">
                  <Sparkles size={16} /> {readinessLabel(agentSpec.readiness)}
                </span>
                <span className={`sprite-sheet mini-sprite sprite-${readinessSprite(agentSpec.readiness)}`} aria-hidden="true" />
              </div>
              <p className="refinery-headline">{agentSpec.headline}</p>
              <div className="refinery-stats">
                <Metric label="Strengths" value={String(agentSpec.strengths.length)} />
                <Metric label="Gaps" value={String(agentSpec.gaps.length)} />
                <Metric label="Helpers" value={String(agentSpec.sub_agents.length)} />
              </div>
              {agentSpec.sub_agents.length > 0 && (
                <div className="subagent-rail">
                  {agentSpec.sub_agents.slice(0, 4).map((sub) => (
                    <div className="subagent-chip" key={sub.id} title={sub.trigger}>
                      <span className={`sprite-sheet mini-sprite sprite-${sub.sprite}`} aria-hidden="true" />
                      <span className="subagent-chip-copy">
                        <strong>{sub.name}</strong>
                        <small>{sub.focus}</small>
                      </span>
                      <span className={`pill ${sub.priority === "recommended" ? "ready" : "planned"}`}>
                        {sub.priority === "recommended" ? "rec" : "opt"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="library-actions">
                <button className="command-button" type="button" onClick={openTraceDrawer}>
                  <Bot size={16} />
                  View plan
                </button>
                {agentMarkdownHref && (
                  <a className="command-button" href={agentMarkdownHref} download={agentMarkdownFilename}>
                    <Save size={16} />
                    Export spec
                  </a>
                )}
                <button className="command-button" type="button" onClick={writeAgentSpecFiles}>
                  <Save size={16} />
                  Write files
                </button>
              </div>
              <div className="library-actions">
                <button
                  className="command-button"
                  type="button"
                  onClick={() => runResearch("fast")}
                  disabled={researchBusy !== null}
                  title="One OpenAI reasoning call grounded in this run"
                >
                  <Sparkles size={16} />
                  {researchBusy === "fast" ? "Researching..." : "OpenAI research"}
                </button>
                <button
                  className="command-button"
                  type="button"
                  onClick={() => runResearch("deep")}
                  disabled={researchBusy !== null}
                  title="OpenAI web-search deep research; can take a few minutes"
                >
                  <Sparkles size={16} />
                  {researchBusy === "deep" ? "Deep researching..." : "Deep research (web)"}
                </button>
              </div>
              {agentResearch && agentResearch.status !== "ok" && (
                <p className="refinery-note">
                  OpenAI research {agentResearch.status}: {agentResearch.message}
                </p>
              )}
              {agentExport && (
                <div className="artifact-card">
                  <span>Agent export</span>
                  <strong>{agentExport.sub_agent_count} helper files</strong>
                  <small>{agentExport.directory}</small>
                </div>
              )}
            </>
          ) : (
            <div className="refinery-empty">
              <p>Run an evaluation to create a coaching plan and focused helper recommendations.</p>
              <button className="command-button" type="button" onClick={refreshAgentSpec} disabled={!scorecard && !run}>
                <Sparkles size={16} />
                Build plan
              </button>
            </div>
          )}
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
              <div className="ledger-row-group" key={item.id} style={{ display: "flex", alignItems: "stretch", gap: 6 }}>
                <button className="ledger-row" type="button" style={{ flex: 1 }} onClick={() => loadPersistedRun(item.id)}>
                  <span className={`sprite-sheet mini-sprite sheet-runs sprite-${runSprite(item.status)}`} aria-hidden="true" />
                  <span>
                    <strong>{item.id}</strong>
                    <small>{item.status} / {item.exam_pack_id}</small>
                  </span>
                  <span>{item.k}x</span>
                </button>
                <Link
                  className="icon-button"
                  href={`/runs/${item.id}`}
                  title={`Open run ${item.id} in its own page`}
                  aria-label={`Open run ${item.id}`}
                >
                  <PanelRightOpen size={16} />
                </Link>
              </div>
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
            {scorecard?.failure_reasons.map((failure, index) => (
              <div className="failure-row" key={`${index}-${failure}`}>{failure}</div>
            ))}
            {error && <p className="error-text">{error}</p>}
          </section>
        ) : null}
      </aside>
        </div>
      </details>

      <TraceDrawer
        events={events}
        trace={trace}
        scorecard={scorecard}
        proofBundle={proofBundle}
        agentSpec={agentSpec}
        agentResearch={agentResearch}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
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

function MetricTile({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "pass" | "warn" }) {
  return (
    <div className={`metric-tile ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function buildJobScope(text: string): JobScope {
  return {
    raw_text: text,
    title: "",
    seniority: "unspecified",
    responsibilities: [],
    required_skills: [],
    nice_to_have: [],
    qualifications: [],
    domain: "",
    risks: [],
    compliance_flags: [],
    extraction: "none"
  };
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
