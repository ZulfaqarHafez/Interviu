import * as React from "react";
import {
  Scale, CheckCircle2, XCircle, Gavel, BadgeCheck, Gauge, BookOpen, ScrollText,
  Sparkles, Inbox, Library, BookCheck, Pin, Clock, Loader2, Check, Eye, EyeOff,
  GitCommitHorizontal, MapPin, Bot, SearchCheck, ClipboardCheck, FileText,
  ShieldCheck, ShieldAlert, HelpCircle, FileCheck2, FileSearch, Lock, Terminal,
  PartyPopper, Target, Cpu, ScanLine, Database, Package, Plug, RadioTower,
  Triangle, AlertTriangle, Circle, TrendingUp, type LucideIcon
} from "lucide-react";
import { cn } from "@/lib/cn";

/** Legacy sheet hint, kept for API compatibility (no longer affects rendering). */
export type SpriteSheet = "dojo" | "judging" | "lessons" | "runs";

type Tone = "accent" | "pass" | "warn" | "fail" | "muted";

const TONE_COLOR: Record<Tone, string> = {
  accent: "var(--teal)",
  pass: "var(--color-pass)",
  warn: "var(--color-warn)",
  fail: "var(--color-fail)",
  muted: "var(--color-fg-muted)"
};

/**
 * Maps a sprite name to a refined vector icon + semantic tone. Replaces the old
 * pixel-art sprite sheets. Names without the `sprite-` prefix, matching the
 * identifiers produced by lib/derive.ts and components/trace/spanMeta.ts.
 */
const ICONS: Record<string, [LucideIcon, Tone]> = {
  // judging
  "grader-deliberating": [Scale, "accent"],
  "grader-approve": [CheckCircle2, "pass"],
  "grader-reject": [XCircle, "fail"],
  "grader-disagreement": [Scale, "warn"],
  gavel: [Gavel, "accent"],
  "verdict-sealed": [BadgeCheck, "pass"],
  "score-meter-low": [Gauge, "fail"],
  "score-meter-mid": [Gauge, "warn"],
  "score-meter-high": [Gauge, "pass"],
  // lessons
  "lesson-book": [BookOpen, "accent"],
  "lesson-scroll": [ScrollText, "accent"],
  "new-lesson-stamp": [Sparkles, "accent"],
  "library-empty": [Inbox, "muted"],
  "library-few": [Library, "accent"],
  "library-many": [Library, "accent"],
  "lesson-applied": [BookCheck, "pass"],
  "lesson-pinned": [Pin, "accent"],
  // runs
  "run-queued": [Clock, "muted"],
  "run-running": [Loader2, "warn"],
  "run-complete": [CheckCircle2, "pass"],
  "pass-bead": [Check, "pass"],
  "fail-bead": [XCircle, "fail"],
  "seen-trial": [Eye, "accent"],
  "held-out-trial": [EyeOff, "accent"],
  "timeline-node": [GitCommitHorizontal, "accent"],
  "learning-trend": [TrendingUp, "accent"],
  "current-phase-marker": [MapPin, "accent"],
  // candidates / actors
  candidate: [Bot, "accent"],
  "candidate-thinking": [Bot, "warn"],
  "candidate-pass": [CheckCircle2, "pass"],
  "candidate-fail": [XCircle, "fail"],
  "candidate-ready": [BadgeCheck, "accent"],
  "candidate-approved": [CheckCircle2, "pass"],
  "candidate-review": [SearchCheck, "accent"],
  "candidate-audit": [ClipboardCheck, "accent"],
  "candidate-document": [FileText, "accent"],
  "candidate-shield": [ShieldCheck, "pass"],
  "candidate-alert": [ShieldAlert, "fail"],
  "candidate-question": [HelpCircle, "warn"],
  "candidate-proof": [FileCheck2, "pass"],
  "candidate-evidence": [FileSearch, "accent"],
  "candidate-lock": [Lock, "accent"],
  "candidate-terminal": [Terminal, "accent"],
  "candidate-celebrate": [PartyPopper, "pass"],
  "candidate-calm": [Bot, "accent"],
  domain: [Target, "accent"],
  judge: [Scale, "accent"],
  simulator: [Cpu, "accent"],
  tracerazor: [ScanLine, "accent"],
  // connectors / scenarios
  supabase: [Database, "accent"],
  "hugging-face": [Package, "accent"],
  vercel: [Triangle, "accent"],
  "injection-scroll": [ScrollText, "fail"],
  "tool-trap": [AlertTriangle, "warn"],
  "privacy-vault": [Lock, "accent"],
  "dataset-crate": [Package, "accent"],
  "mcp-plug": [Plug, "accent"],
  "model-chip": [Cpu, "accent"],
  "http-antenna": [RadioTower, "accent"],
  "local-command": [Terminal, "accent"],
  "audit-shard": [ShieldCheck, "accent"]
};

export type SpriteProps = Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & {
  /** Icon name without the `sprite-` prefix, e.g. "candidate-approved". */
  name: string;
  /** Legacy sheet hint, ignored (kept for call-site compatibility). */
  sheet?: SpriteSheet;
  /** Scale multiplier; the base icon is 18px. */
  scale?: number;
  /** Spin the icon (e.g. an in-progress run). */
  thinking?: boolean;
};

/**
 * Renders a refined vector icon for a sprite name, tinted by semantic tone.
 * Replaces the former pixel-art sprite system while preserving its call API.
 */
export const Sprite = React.forwardRef<HTMLSpanElement, SpriteProps>(function Sprite(
  { name, sheet: _sheet = undefined, scale = 1, thinking, className, style, ...props },
  ref
) {
  void _sheet;
  const [Icon, tone] = ICONS[name] ?? [Circle, "accent"];
  const size = Math.round(18 * scale);
  const spin = Boolean(thinking) || name === "run-running";
  return (
    <span
      ref={ref}
      aria-hidden="true"
      className={cn("assay-icon", className)}
      style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", color: TONE_COLOR[tone], ...style }}
      {...props}
    >
      <Icon size={size} strokeWidth={scale >= 2 ? 1.5 : 1.75} className={spin ? "assay-spin" : undefined} />
    </span>
  );
});

export default Sprite;
