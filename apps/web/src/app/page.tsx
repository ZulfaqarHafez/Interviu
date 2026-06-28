"use client";

import { useEffect, useMemo, useState } from "react";
import { assayApi } from "@/lib/api";
import {
  useCandidates,
  useExamPacks,
  useHealth,
  useRuns
} from "@/lib/queries";
import { useRunStream } from "@/lib/useRunStream";
import { errorMessage, type LoadState } from "@/lib/derive";
import TraceDrawer from "@/components/trace/TraceDrawer";
import AgentIntake from "@/components/assay/AgentIntake";
import Landing from "@/components/assay/Landing";
import JudgingWaterfall from "@/components/assay/JudgingWaterfall";
import VerdictPanel from "@/components/assay/VerdictPanel";
import { AGENT_TEMPLATES } from "@/lib/assayTemplates";
import type {
  AgentResearch,
  AgentSpec,
  CandidateConfig,
  ProofBundle,
  RunEvent,
  RunRecord,
  Scorecard,
  TracePayload
} from "@/types/assay";

export default function Home() {
  // Boot data via TanStack Query (cache, retry, dedupe handled by the client).
  const healthQuery = useHealth();
  const examPacksQuery = useExamPacks();
  const candidatesQuery = useCandidates();
  const runsQuery = useRuns();

  const health = healthQuery.data ?? null;
  const examPacks = useMemo(() => examPacksQuery.data ?? [], [examPacksQuery.data]);
  const candidates = useMemo(() => candidatesQuery.data ?? [], [candidatesQuery.data]);

  const bootLoading =
    healthQuery.isLoading ||
    examPacksQuery.isLoading ||
    candidatesQuery.isLoading ||
    runsQuery.isLoading;

  // Run-scoped state set imperatively once a run resolves.
  const [selectedExamPackId, setSelectedExamPackId] = useState("hr-v1");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [extraCandidates, setExtraCandidates] = useState<CandidateConfig[]>([]);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [trace, setTrace] = useState<TracePayload | null>(null);
  const [proofBundle, setProofBundle] = useState<ProofBundle | null>(null);
  const [agentSpec, setAgentSpec] = useState<AgentSpec | null>(null);
  const [agentResearch, setAgentResearch] = useState<AgentResearch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  // Map run-stream lifecycle onto the LoadState used to drive the phase.
  const state: LoadState = useMemo(() => {
    if (runStream.status === "queued" || runStream.status === "running") return "running";
    if (error || runStream.status === "failed") return "error";
    if (scorecard) return "complete";
    if (bootLoading) return "loading";
    return "idle";
  }, [runStream.status, error, scorecard, bootLoading]);

  const isRunning = state === "running";

  const selectedExamPack = examPacks.find((pack) => pack.id === selectedExamPackId) ?? examPacks[0];

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

  function resetRunArtifacts() {
    setEvents([]);
    setScorecard(null);
    setTrace(null);
    setProofBundle(null);
    setAgentSpec(null);
    setAgentResearch(null);
  }

  async function hydrateRunArtifacts(runId: string) {
    try {
      const [eventPayload, tracePayload, bundlePayload] = await Promise.all([
        assayApi.events(runId),
        assayApi.trace(runId),
        assayApi.proofBundle(runId)
      ]);
      setEvents(eventPayload);
      setTrace(tracePayload);
      setProofBundle(bundlePayload);
      setAgentSpec(bundlePayload.agent_spec ?? null);
      void runsQuery.refetch();
    } catch (exc) {
      setError(errorMessage(exc));
    }
  }

  // Assay primary flow: take an uploaded/authored agent.md, register it as the
  // candidate under test (live LLM when a key is set, deterministic demo when
  // not), then immediately run the adversarial exam and stream the judging.
  async function runAgentMarkdown(markdown: string, roleScopeText?: string) {
    if (!markdown.trim()) return;
    setError(null);
    resetRunArtifacts();
    runStream.reset();
    setRun(null);
    setIntakeSubmitting(true);
    try {
      const intake = await assayApi.candidateFromMarkdown(markdown);
      const created = intake.candidate;
      setExtraCandidates((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setSelectedCandidateId(created.id);
      void candidatesQuery.refetch();
      const packId = selectedExamPack?.id ?? selectedExamPackId ?? "hr-v1";
      const jobScope = roleScopeText?.trim()
        ? {
            raw_text: roleScopeText.trim(),
            title: "",
            seniority: "unspecified" as const,
            responsibilities: [],
            required_skills: [],
            nice_to_have: [],
            qualifications: [],
            domain: "",
            risks: [],
            compliance_flags: [],
            extraction: "none" as const
          }
        : null;
      const createdRun = await assayApi.createRun(created.id, packId, jobScope);
      const runPack = examPacks.find((pack) => pack.id === createdRun.exam_pack_id) ?? selectedExamPack;
      setRun(createdRun);
      runStream.start(createdRun.id, { k: createdRun.k, itemCount: runPack?.items.length });
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setIntakeSubmitting(false);
    }
  }

  function cancelRun() {
    runStream.cancel();
  }

  // Return to the calm intake screen to test another agent.
  function testAnother() {
    setError(null);
    resetRunArtifacts();
    runStream.reset();
    setRun(null);
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
        const [tracePayload, bundlePayload] = await Promise.all([
          assayApi.trace(runId),
          assayApi.proofBundle(runId)
        ]);
        setEvents(tracePayload.events);
        setTrace(tracePayload);
        setProofBundle(bundlePayload);
        setAgentSpec(bundlePayload.agent_spec ?? null);
      } catch (exc) {
        setError(errorMessage(exc));
      }
    }
    setDrawerOpen(true);
  }

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
