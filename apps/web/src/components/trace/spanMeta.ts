import type { RunEvent } from "@/types/assay";

/**
 * Per-actor visual metadata shared by SpanTree and SpanDetail so the trace view
 * stays color-consistent. Colors reference semantic tokens (light + dark safe).
 */
export type ActorMeta = {
  /** CSS color (token reference) for the span's accent. */
  color: string;
  /** Human label for the actor lane. */
  label: string;
  /** Sprite name (dojo/judging/lessons/runs sheets) used as a compact accent. */
  sprite: string;
  /** Sprite sheet the sprite lives on. */
  sheet: "dojo" | "judging" | "lessons" | "runs";
};

export const ACTOR_META: Record<RunEvent["actor"], ActorMeta> = {
  candidate: { color: "var(--color-accent)", label: "Candidate", sprite: "candidate", sheet: "dojo" },
  examiner: { color: "var(--color-info)", label: "Examiner", sprite: "domain", sheet: "dojo" },
  grader_panel: { color: "var(--color-warn)", label: "Judge panel", sprite: "grader-deliberating", sheet: "judging" },
  lesson_library: { color: "var(--color-pass)", label: "Lesson library", sprite: "lesson-book", sheet: "lessons" },
  trace_auditor: { color: "var(--color-info)", label: "Trace auditor", sprite: "tracerazor", sheet: "dojo" },
  system: { color: "var(--color-fg-muted)", label: "System", sprite: "simulator", sheet: "dojo" }
};

/** Resolve actor meta with a safe fallback to the system lane. */
export function actorMeta(actor: RunEvent["actor"]): ActorMeta {
  return ACTOR_META[actor] ?? ACTOR_META.system;
}
