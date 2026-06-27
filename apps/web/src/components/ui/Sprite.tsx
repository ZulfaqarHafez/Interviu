import * as React from "react";
import { cn } from "@/lib/cn";

/** Which pixel-art sprite sheet a name belongs to. "dojo" is the default sheet. */
export type SpriteSheet = "dojo" | "judging" | "lessons" | "runs";

const SHEET_CLASS: Record<SpriteSheet, string> = {
  dojo: "",
  judging: "sheet-judging",
  lessons: "sheet-lessons",
  runs: "sheet-runs"
};

export type SpriteProps = Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & {
  /** Sprite name without the `sprite-` prefix, e.g. "candidate-approved". */
  name: string;
  /** Source sheet. Defaults to the dojo sheet. */
  sheet?: SpriteSheet;
  /** Scale multiplier applied via the --sprite-scale custom property. */
  scale?: number;
  /** Add the existing `thinking` animation class. */
  thinking?: boolean;
};

/**
 * Renders a pixel-art sprite by composing the existing globals.css sprite
 * classes (.sprite-sheet + optional sheet-* + sprite-<name>). Keeps the sprite
 * system as the single styling source so accents stay consistent.
 */
export const Sprite = React.forwardRef<HTMLSpanElement, SpriteProps>(function Sprite(
  { name, sheet = "dojo", scale, thinking, className, style, ...props },
  ref
) {
  const scaleStyle = scale !== undefined ? ({ ["--sprite-scale" as string]: String(scale) } as React.CSSProperties) : undefined;
  return (
    <span
      ref={ref}
      aria-hidden="true"
      className={cn("sprite-sheet", SHEET_CLASS[sheet], `sprite-${name}`, thinking && "thinking", className)}
      style={{ ...scaleStyle, ...style }}
      {...props}
    />
  );
});

export default Sprite;
