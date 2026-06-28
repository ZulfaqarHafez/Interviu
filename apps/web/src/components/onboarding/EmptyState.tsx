"use client";

import * as React from "react";
import { Play, Zap, Copy, Check } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Sprite from "@/components/ui/Sprite";
import { useAnnouncer } from "@/components/announcer";
import { useCandidates, useCreateCandidate, useCreateRun, useStartRun } from "@/lib/queries";
import { errorMessage } from "@/lib/derive";
import type { RunRecord, Scorecard } from "@/types/assay";

/**
 * First-run experience shown when there are no runs yet.
 *
 * - "Load demo exam + run demo candidate": creates a mock candidate (if none
 *   exist), creates a run on `hr-v1`, and starts it — the one-click demo path.
 * - "Quick run": the same fast happy path, framed as a minimal pass (k=1).
 * - A copy-paste HTTP-candidate snippet documents the adapter contract so a real
 *   agent can be wired up: POST {context, question} -> {answer, reasoning,
 *   tool_calls, tokens, latency_ms}.
 *
 * Callers may override `onLoadDemo` / `onQuickRun` to integrate with their own
 * run pipeline (e.g. the streaming run UX); otherwise the built-in mutation
 * handlers run a complete demo end to end.
 */
export type EmptyStateProps = {
  examPackId?: string;
  /** Override the demo CTA; receives the started run + scorecard on success. */
  onLoadDemo?: () => void;
  /** Override the quick-run CTA. */
  onQuickRun?: () => void;
  /** Notified when an internal demo/quick run completes. */
  onRunComplete?: (run: RunRecord, scorecard: Scorecard) => void;
};

const ADAPTER_SNIPPET = `# Assay HTTP candidate contract
# Assay POSTs each interview turn to your endpoint:
#   POST https://your-agent.example.com/ask
#   { "context": "...", "question": "..." }
# Respond with:
#   {
#     "answer": "...",          # the agent's reply
#     "reasoning": "...",       # optional chain-of-thought / notes
#     "tool_calls": [],         # optional list of tool invocations
#     "tokens": 128,            # tokens used this turn
#     "latency_ms": 540         # turn latency in milliseconds
#   }

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Ask(BaseModel):
    context: str
    question: str

@app.post("/ask")
def ask(payload: Ask):
    return {
        "answer": "Rank candidates only on job-related criteria.",
        "reasoning": "Protected traits must not influence ranking.",
        "tool_calls": [],
        "tokens": 128,
        "latency_ms": 540,
    }`;

export function EmptyState({
  examPackId = "hr-v1",
  onLoadDemo,
  onQuickRun,
  onRunComplete
}: EmptyStateProps) {
  const { announce } = useAnnouncer();
  const candidatesQuery = useCandidates();
  const createCandidate = useCreateCandidate();
  const createRun = useCreateRun();
  const startRun = useStartRun();

  const [busy, setBusy] = React.useState<null | "demo" | "quick">(null);
  const [error, setError] = React.useState<string | null>(null);

  const pending = busy !== null;

  const runDemo = React.useCallback(
    async (kind: "demo" | "quick") => {
      setBusy(kind);
      setError(null);
      announce(kind === "quick" ? "Starting a quick run" : "Loading the demo run");
      try {
        const existing = candidatesQuery.data?.find((candidate) => candidate.adapter_type === "mock");
        const candidate =
          existing ??
          (await createCandidate.mutateAsync({
            name: "Demo Candidate",
            adapter_type: "mock",
            metadata: { source: "onboarding" }
          }));
        const run = await createRun.mutateAsync({ candidateId: candidate.id, examPackId });
        const scorecard = await startRun.mutateAsync(run.id);
        announce(
          scorecard.certified ? "Demo run passed" : "Demo run completed, needs review",
          { assertive: false }
        );
        onRunComplete?.(run, scorecard);
      } catch (exc) {
        const message = errorMessage(exc);
        setError(message);
        announce(`Demo run failed: ${message}`, { assertive: true });
      } finally {
        setBusy(null);
      }
    },
    [announce, candidatesQuery.data, createCandidate, createRun, startRun, examPackId, onRunComplete]
  );

  const handleDemo = onLoadDemo ?? (() => void runDemo("demo"));
  const handleQuick = onQuickRun ?? (() => void runDemo("quick"));

  return (
    <Card aria-label="Get started" style={{ maxWidth: 760 }}>
      <CardHeader>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <Sprite name="candidate-ready" scale={1.2} />
          <strong style={{ fontSize: 15 }}>Run your first evaluation</strong>
        </span>
        <Badge variant="neutral">No runs yet</Badge>
      </CardHeader>
      <CardBody style={{ display: "grid", gap: 16 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--color-fg-muted)", lineHeight: 1.5 }}>
          Assay interviews an AI agent against an adversarial exam, grades it, audits its trace,
          and writes a coaching plan. Start with the built-in demo, then wire up your own agent over
          the HTTP contract below.
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <Button variant="primary" onClick={handleDemo} disabled={pending}>
            <Play size={16} />
            {busy === "demo" ? "Running demo…" : "Load demo exam + run demo candidate"}
          </Button>
          <Button variant="ghost" onClick={handleQuick} disabled={pending}>
            <Zap size={16} />
            {busy === "quick" ? "Running…" : "Quick run (k=1)"}
          </Button>
        </div>

        {error && (
          <p role="alert" style={{ margin: 0, fontSize: 12, color: "var(--color-fail)" }}>
            {error}
          </p>
        )}

        <AdapterSnippet />
      </CardBody>
    </Card>
  );
}

function AdapterSnippet() {
  const [copied, setCopied] = React.useState(false);
  const { announce } = useAnnouncer();

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(ADAPTER_SNIPPET);
      setCopied(true);
      announce("Adapter snippet copied");
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard may be unavailable (e.g. insecure context); fail silently.
    }
  }, [announce]);

  return (
    <section style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Sprite name="http-antenna" />
          <strong style={{ fontSize: 13 }}>Connect your own agent (HTTP)</strong>
        </span>
        <Button variant="ghost" size="sm" onClick={handleCopy} aria-label="Copy adapter snippet">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre
        style={{
          margin: 0,
          fontSize: 12,
          lineHeight: 1.5,
          background: "var(--color-soft)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "12px 14px",
          overflowX: "auto",
          color: "var(--color-fg)"
        }}
      >
        <code>{ADAPTER_SNIPPET}</code>
      </pre>
    </section>
  );
}

export default EmptyState;
