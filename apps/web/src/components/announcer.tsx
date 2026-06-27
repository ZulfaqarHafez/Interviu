"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

export type AnnounceOptions = {
  /** Use the assertive (role="alert") live region instead of the polite one. */
  assertive?: boolean;
};

type AnnouncerContextValue = {
  /** Push a message into an ARIA live region for screen-reader users. */
  announce: (message: string, options?: AnnounceOptions) => void;
};

const AnnouncerContext = createContext<AnnouncerContextValue | null>(null);

/**
 * Provides two always-present ARIA live regions (polite + assertive) and an
 * `announce` function. Mount once near the root; consume with `useAnnouncer`.
 */
export function AnnouncerProvider({ children }: { children: React.ReactNode }) {
  const [polite, setPolite] = useState("");
  const [assertive, setAssertive] = useState("");
  // Clearing then re-setting forces SRs to re-read identical consecutive messages.
  const politeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const assertiveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const announce = useCallback((message: string, options?: AnnounceOptions) => {
    if (!message) return;
    if (options?.assertive) {
      setAssertive("");
      if (assertiveTimer.current) clearTimeout(assertiveTimer.current);
      assertiveTimer.current = setTimeout(() => setAssertive(message), 50);
    } else {
      setPolite("");
      if (politeTimer.current) clearTimeout(politeTimer.current);
      politeTimer.current = setTimeout(() => setPolite(message), 50);
    }
  }, []);

  const value = useMemo<AnnouncerContextValue>(() => ({ announce }), [announce]);

  return (
    <AnnouncerContext.Provider value={value}>
      {children}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {polite}
      </div>
      <div role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
        {assertive}
      </div>
    </AnnouncerContext.Provider>
  );
}

/**
 * Returns the `announce(message, { assertive? })` function. Safe to call when no
 * provider is mounted (e.g. in unit tests) — it becomes a no-op.
 */
export function useAnnouncer(): AnnouncerContextValue {
  const ctx = useContext(AnnouncerContext);
  if (!ctx) {
    return { announce: () => {} };
  }
  return ctx;
}

export default AnnouncerProvider;
