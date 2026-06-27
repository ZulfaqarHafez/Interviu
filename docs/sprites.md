# Pixel Sprite Assets

Interviu now has two sprite assets:

- `apps/web/public/sprites/interviu-dojo-sprites.svg`: deterministic 32px grid sprite sheet used by the app.
- `apps/web/public/sprites/interviu-dojo-generated-concept.png`: AI-generated concept sheet used as visual direction.
- `apps/web/public/sprites/interviu-character-expanded-concept.png`: AI-generated character-state concept sheet used for the expanded character row.

The app renders from the SVG sheet so browser output is stable and testable. The generated PNG is kept as a creative reference for future richer sprite passes.

## Sprite Manifest

`apps/web/public/sprites/interviu-dojo-sprites.json` defines the tile coordinates. Each tile is 32px, and CSS scales hero sprites to 96px with `image-rendering: pixelated`.

Current sprites include candidate states, examiners, judge panel, simulator, TraceRazor, Supabase, Hugging Face, Vercel, pass/fail badges, prompt injection tiles, tool-output traps, privacy vaults, dataset export crates, MCP plugs, model chips, HTTP antennas, local command terminals, audit shards, and expanded character rows with walking, shield, document, audit, celebration, tired, terminal, privacy-lock, ready, question, evidence, review, approved, alert, export, proof, and calm poses.

The SVG sheet is now five rows of nine 32px tiles. Keep `background-size` in `apps/web/src/app/globals.css` aligned with the sheet dimensions when adding more rows.
