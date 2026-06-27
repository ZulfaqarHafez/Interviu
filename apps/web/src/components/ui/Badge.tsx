import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badge = cva("ui-badge", {
  variants: {
    variant: {
      pass: "ui-badge--pass",
      warn: "ui-badge--warn",
      fail: "ui-badge--fail",
      ready: "ui-badge--ready",
      planned: "ui-badge--planned",
      neutral: "ui-badge--neutral"
    }
  },
  defaultVariants: {
    variant: "neutral"
  }
});

type BadgeVariant = NonNullable<VariantProps<typeof badge>["variant"]>;

const VARIANT_STYLE: Record<BadgeVariant, React.CSSProperties> = {
  pass: { background: "var(--color-pass-bg)", color: "var(--color-pass)", borderColor: "var(--color-pass)" },
  warn: { background: "var(--color-warn-bg)", color: "var(--color-warn)", borderColor: "var(--color-warn)" },
  fail: { background: "var(--color-fail-bg)", color: "var(--color-fail)", borderColor: "var(--color-fail)" },
  ready: { background: "var(--color-pass-bg)", color: "var(--color-pass)", borderColor: "var(--color-pass)" },
  planned: { background: "var(--color-soft)", color: "var(--color-fg-muted)", borderColor: "var(--color-border)" },
  neutral: { background: "var(--color-soft)", color: "var(--color-fg-muted)", borderColor: "var(--color-border)" }
};

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>;

/** Compact status pill. Variants map to the semantic outcome tokens. */
export function Badge({ className, variant, style, ...props }: BadgeProps) {
  const resolved = (variant ?? "neutral") as BadgeVariant;
  return (
    <span
      className={cn(badge({ variant }), className)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        minHeight: 22,
        padding: "0 8px",
        borderRadius: "var(--radius-pill)",
        border: "1px solid",
        fontSize: 11,
        fontWeight: 700,
        lineHeight: 1,
        ...VARIANT_STYLE[resolved],
        ...style
      }}
      {...props}
    />
  );
}

export { badge as badgeVariants };
export default Badge;
