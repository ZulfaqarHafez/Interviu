import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const button = cva("ui-button", {
  variants: {
    variant: {
      primary: "ui-button--primary",
      ghost: "ui-button--ghost",
      icon: "ui-button--icon"
    },
    size: {
      sm: "ui-button--sm",
      md: "ui-button--md",
      lg: "ui-button--lg"
    }
  },
  defaultVariants: {
    variant: "ghost",
    size: "md"
  }
});

type ButtonVariant = NonNullable<VariantProps<typeof button>["variant"]>;
type ButtonSize = NonNullable<VariantProps<typeof button>["size"]>;

const SIZE_STYLE: Record<ButtonSize, React.CSSProperties> = {
  sm: { padding: "6px 10px", fontSize: 12, gap: 6 },
  md: { padding: "8px 14px", fontSize: 13, gap: 8 },
  lg: { padding: "10px 18px", fontSize: 14, gap: 8 }
};

const VARIANT_STYLE: Record<ButtonVariant, React.CSSProperties> = {
  primary: { background: "var(--color-accent)", color: "var(--color-accent-fg)", borderColor: "var(--color-accent)" },
  ghost: { background: "var(--color-panel)", color: "var(--color-fg)", borderColor: "var(--color-border)" },
  icon: { background: "var(--color-panel)", color: "var(--color-fg)", borderColor: "var(--color-border)" }
};

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>;

/**
 * Token-styled button. Variants: primary / ghost / icon. The `icon` variant is
 * a square affordance for toolbar icons; pair it with an aria-label.
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, type, style, ...props },
  ref
) {
  const resolvedVariant = (variant ?? "ghost") as ButtonVariant;
  const resolvedSize = (size ?? "md") as ButtonSize;
  const iconStyle: React.CSSProperties =
    resolvedVariant === "icon"
      ? { width: 36, height: 36, padding: 0, justifyContent: "center" }
      : SIZE_STYLE[resolvedSize];
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={cn(button({ variant, size }), className)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        borderRadius: "var(--radius-md)",
        border: "1px solid",
        fontWeight: 700,
        cursor: "pointer",
        transition: "background 120ms ease, border-color 120ms ease, transform 120ms ease",
        ...VARIANT_STYLE[resolvedVariant],
        ...iconStyle,
        ...style
      }}
      {...props}
    />
  );
});

export { button as buttonVariants };
export default Button;
