# Pixel Sprite Assets

Assay now has two sprite assets:

- `apps/web/public/sprites/assay-dojo-sprites.svg`: deterministic 32px grid sprite sheet used by the app.
- `apps/web/public/sprites/assay-dojo-generated-concept.png`: AI-generated concept sheet used as visual direction.
- `apps/web/public/sprites/assay-character-expanded-concept.png`: AI-generated character-state concept sheet used for the expanded character row.

The app renders from the SVG sheet so browser output is stable and testable. The generated PNG is kept as a creative reference for future richer sprite passes.

## Premium duotone palette (light + dark)

The sheets were restyled from the original saturated "candy" look to a premium,
editorial, **duotone-tinted-by-state** treatment. Each of the four sheets ships
**two variants**:

- `assay-<sheet>-sprites.svg` — the **light** sheet (Muted Editorial palette).
- `assay-<sheet>-sprites-dark.svg` — the **dark** sheet (Premium Terminal
  palette). Geometry and tile coordinates are byte-identical to the light file;
  only the `<defs><style>` palette block differs.

Sheets: `dojo`, `judging`, `lessons`, `runs` → 8 SVGs total.

Both variants are **background-transparent** (the old baked
`<rect fill="#fbfaf7"/>` was removed) so tiles composite onto the app surface in
either theme.

### Palette classes

The class **names are stable** (`.k .w .t .g .r .y .v .m .b`) so existing tile
classes and the JSON manifests keep working unchanged — only the hex values
change between variants. Each main material also exposes a **3-step ramp** added
to the palette block for selout shading (light source is always **top-left**):
`.t2/.g2/.r2/.y2` = cooler/darker shadow, `.t3/.g3/.r3/.y3` = warmer/lighter
highlight; `.k2` = deeper ink, `.ke` = broken-outline selout edge. Semantics are
unchanged: grass `.g` = pass/approve, coral `.r` = fail/reject, gold `.y` =
queued/caution, teal/accent `.t` = active/running, violet/info `.v` = meta/marker.

| Class | Light (Muted Editorial) | Dark (Premium Terminal) |
| --- | --- | --- |
| `.k` ink outline | `#1c1a17` | `#0a0f15` |
| `.k2` deep ink | `#0f0e0c` | `#050709` |
| `.ke` selout edge | `#4a463f` | `#2a3340` |
| `.w` glint | `#ffffff` | `#ffffff` |
| `.t` teal/accent | `#0f6b5f` | `#3b9eff` |
| `.g` pass | `#1f7a52` | `#3dd68c` |
| `.r` fail | `#b5392f` | `#ff9592` |
| `.y` warn | `#a25e10` | `#ffca16` |
| `.v` meta/info | `#3a6ea5` | `#70b8ff` |
| `.m` neutral | `#6b6760` | `#8a93a0` |
| `.b` blue | `#3a6ea5` | `#70b8ff` |

(`.t/.g/.r/.y` each have matching `…2` shadow and `…3` highlight steps in the
`<defs><style>` block of every sheet.)

### Theme wiring

The JSON manifests do **not** change — they always point at the light SVG. The
dark variant is swapped in by CSS: under `.dark`, `apps/web/src/app/globals.css`
re-points each sheet's `--sprite-sheet-url` at the `…-dark.svg` file. Dark
filenames for the CSS wiring:

- `/sprites/assay-dojo-sprites-dark.svg`
- `/sprites/assay-judging-sprites-dark.svg`
- `/sprites/assay-lessons-sprites-dark.svg`
- `/sprites/assay-runs-sprites-dark.svg`

## Sprite Manifest

`apps/web/public/sprites/assay-dojo-sprites.json` defines the tile coordinates. Each tile is 32px, and CSS scales hero sprites to 96px with `image-rendering: pixelated`.

Current sprites include candidate states, examiners, judge panel, simulator, TraceRazor, Supabase, Hugging Face, Vercel, pass/fail badges, prompt injection tiles, tool-output traps, privacy vaults, dataset export crates, MCP plugs, model chips, HTTP antennas, local command terminals, audit shards, and expanded character rows with walking, shield, document, audit, celebration, tired, terminal, privacy-lock, ready, question, evidence, review, approved, alert, export, proof, and calm poses.

The SVG sheet is now five rows of nine 32px tiles. Keep `background-size` in `apps/web/src/app/globals.css` aligned with the sheet dimensions when adding more rows.

## Agent Panel and Refinery Sprites

The arena "agent panel" spawns the interview cast from this sheet: the examiner
(`domain`), judge panel (`judge`), lesson library (`candidate-document`),
TraceRazor auditor (`tracerazor`), and simulator (`simulator`) tiles render as
roster characters that activate while a run is in flight.

The Agent Refinery reuses candidate-state tiles for its sub-agent
recommendations — the backend emits a `sprite` class suffix per sub-agent (for
example `candidate-shield` for an untrusted-input firewall, `candidate-lock` for
a privacy steward, `tracerazor` for the Trace Auditor) and the web app renders it
as `sprite-<suffix>`. Readiness verdicts use `candidate-approved`,
`candidate-question`, and `candidate-review`.

## Additional Sheets: Judging / Lessons / Runs

Beyond the 9×5 `dojo` sheet, Assay ships three single-row companion sheets,
each a deterministic 9×1 (288×32) SVG plus a sibling JSON manifest under
`apps/web/public/sprites/`. They keep the dojo sheet focused on characters while
giving runtime state its own glyphs.

### `assay-judging-sprites` (grader panel state)

| Tile | Manifest key | CSS class |
| --- | --- | --- |
| Grader deliberating | `graderDeliberating` | `sprite-grader-deliberating` |
| Grader approve | `graderApprove` | `sprite-grader-approve` |
| Grader reject | `graderReject` | `sprite-grader-reject` |
| Gavel | `gavel` | `sprite-gavel` |
| Score meter (low) | `scoreMeterLow` | `sprite-score-meter-low` |
| Score meter (mid) | `scoreMeterMid` | `sprite-score-meter-mid` |
| Score meter (high) | `scoreMeterHigh` | `sprite-score-meter-high` |
| Grader disagreement | `graderDisagreement` | `sprite-grader-disagreement` |
| Verdict sealed | `verdictSealed` | `sprite-verdict-sealed` |

### `assay-lessons-sprites` (lesson library growth)

| Tile | Manifest key | CSS class |
| --- | --- | --- |
| Lesson scroll | `lessonScroll` | `sprite-lesson-scroll` |
| Lesson book | `lessonBook` | `sprite-lesson-book` |
| New lesson stamp | `newLessonStamp` | `sprite-new-lesson-stamp` |
| Library empty | `libraryEmpty` | `sprite-library-empty` |
| Library few | `libraryFew` | `sprite-library-few` |
| Library many | `libraryMany` | `sprite-library-many` |
| Lesson applied | `lessonApplied` | `sprite-lesson-applied` |
| Lesson pinned | `lessonPinned` | `sprite-lesson-pinned` |

### `assay-runs-sprites` (run status / timeline)

| Tile | Manifest key | CSS class |
| --- | --- | --- |
| Run queued | `runQueued` | `sprite-run-queued` |
| Run running | `runRunning` | `sprite-run-running` |
| Seen trial | `seenTrial` | `sprite-seen-trial` |
| Held-out trial | `heldOutTrial` | `sprite-held-out-trial` |
| Pass bead | `passBead` | `sprite-pass-bead` |
| Fail bead | `failBead` | `sprite-fail-bead` |
| Run complete | `runComplete` | `sprite-run-complete` |
| Current phase marker | `currentPhaseMarker` | `sprite-current-phase-marker` |
| Timeline node | `timelineNode` | `sprite-timeline-node` |

### CSS model

These sheets use the same `.sprite-sheet` base, which now drives
`background-size` from CSS variables instead of a fixed pixel size:

- `.sprite-sheet` reads `--sprite-cols`, `--sprite-rows`, `--sprite-x`,
  `--sprite-y`, and `--sprite-scale`; `background-size` is computed as
  `32px * cols * scale` by `32px * rows * scale`, and `background-position` from
  `--sprite-x` / `--sprite-y`. This makes any sheet shape work without editing the
  base rule.
- A `.sheet-<name>` class swaps in the sheet and its grid:
  `.sheet-judging`, `.sheet-lessons`, and `.sheet-runs` each set
  `--sprite-sheet-url` and `--sprite-cols: 9; --sprite-rows: 1;`. The default
  (dojo) base stays at `9×5`.
- Usage is `class="sprite-sheet sheet-<name> sprite-<kebab-name>"`, e.g.
  `sprite-sheet sheet-runs sprite-pass-bead`.

### How the UI uses them

`apps/web/src/app/page.tsx` selects tiles by run state:

- **Roster judge verdict** — the Judge panel roster slot draws from
  `.sheet-judging`: `grader-deliberating` while a run is in flight,
  `grader-approve` when the scorecard is certified, and `grader-reject`
  otherwise.
- **Lessons library growth** — the Lessons roster slot draws from
  `.sheet-lessons`: `new-lesson-stamp` while running, then `library-empty` /
  `library-few` / `library-many` based on how many lessons were kept.
- **Recent-runs status glyph** — each item in the runs list renders a
  `.sheet-runs` mini-sprite via `runSprite(status)`: `run-running`,
  `run-complete`, `fail-bead` (failed), or `run-queued`.

### Extending / regenerating

Use the `sprite-generator` skill (`.claude/skills/sprite-generator/SKILL.md`) to
add tiles, add a whole new sheet, or regenerate a sheet. It documents the SVG
conventions, the palette classes, the manifest shape, and the four-step wiring
(SVG cell → JSON manifest → `.sheet-*` rows bump if needed → `.sprite-*` tile
class), and reminds you to keep this doc updated.

When editing geometry, apply the change to **both** the light
`assay-<sheet>-sprites.svg` and the dark `assay-<sheet>-sprites-dark.svg`
so the two stay coordinate-identical (only their `<defs><style>` palette blocks
differ — see the palette table above). Keep both variants background-transparent.
