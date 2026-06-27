"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

/**
 * Route-level error boundary (App Router convention). Catches render/runtime
 * errors below the root layout and offers a recovery action.
 */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surface to the console so it is visible in dev and in browser logs.
    console.error(error);
  }, [error]);

  return (
    <main className="app-error" role="alert">
      <div className="app-error-card">
        <span className="app-error-icon" aria-hidden="true">
          <AlertTriangle size={28} />
        </span>
        <h1>Something went wrong</h1>
        <p>The evaluation workspace hit an unexpected error and stopped rendering.</p>
        {error?.message ? <pre className="app-error-detail">{error.message}</pre> : null}
        {error?.digest ? <small className="app-error-digest">Reference: {error.digest}</small> : null}
        <button className="command-button primary" type="button" onClick={() => reset()}>
          <RefreshCw size={16} />
          Try again
        </button>
      </div>
    </main>
  );
}
