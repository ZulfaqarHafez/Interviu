import * as React from "react";
import { cn } from "@/lib/cn";

/**
 * Token-styled surface container. Use as the base panel for console sections.
 * Variant `soft` drops the shadow for nested/secondary panels.
 */
export type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "soft";
  as?: React.ElementType;
};

export const Card = React.forwardRef<HTMLDivElement, CardProps>(function Card(
  { className, variant = "default", as, style, ...props },
  ref
) {
  const Component = (as ?? "div") as React.ElementType;
  return (
    <Component
      ref={ref}
      className={cn("ui-card", className)}
      style={{
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-panel)",
        boxShadow: variant === "soft" ? "none" : "var(--shadow-card-soft)",
        color: "var(--color-fg)",
        ...style
      }}
      {...props}
    />
  );
});

export type CardHeaderProps = React.HTMLAttributes<HTMLDivElement>;

export function CardHeader({ className, style, ...props }: CardHeaderProps) {
  return (
    <div
      className={cn("ui-card-header", className)}
      style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 16px", ...style }}
      {...props}
    />
  );
}

export type CardBodyProps = React.HTMLAttributes<HTMLDivElement>;

export function CardBody({ className, style, ...props }: CardBodyProps) {
  return <div className={cn("ui-card-body", className)} style={{ padding: "0 16px 16px", ...style }} {...props} />;
}

export default Card;
