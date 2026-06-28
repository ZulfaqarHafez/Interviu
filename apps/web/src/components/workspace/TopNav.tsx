"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import BrandMark from "@/components/ui/BrandMark";
import { ThemeToggle } from "@/components/ThemeToggle";

/**
 * Persistent platform nav across the whole workspace: the front door ("Test an
 * agent") plus the experimentation surfaces (Experiments / Suites / Agents).
 * Rendered once in the root layout so every route shares it.
 */

const LINKS: { href: string; label: string; exact?: boolean }[] = [
  { href: "/", label: "Test an agent", exact: true },
  { href: "/runs", label: "Experiments" },
  { href: "/suites", label: "Suites" },
  { href: "/agents", label: "Agents" }
];

export function TopNav() {
  const pathname = usePathname() || "/";
  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="ws-nav">
      <div className="ws-nav-inner">
        <Link href="/" className="ws-brand" aria-label="Assay home">
          <BrandMark size={30} className="ws-brand-mark" title="Assay" />
          <span>Assay</span>
        </Link>
        <nav className="ws-links" aria-label="Primary">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`ws-link ${isActive(l.href, l.exact) ? "active" : ""}`}
              aria-current={isActive(l.href, l.exact) ? "page" : undefined}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}

export default TopNav;
