"use client";

import { useEffect } from "react";

/**
 * Top-level error boundary that also catches errors thrown in the root layout.
 * Must render its own <html>/<body>. Styles are inlined because the app's CSS
 * may not be applied when the root layout itself fails.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#f6f7f4",
          color: "#101915",
          fontFamily: "Inter, 'Segoe UI', system-ui, -apple-system, sans-serif"
        }}
      >
        <main
          role="alert"
          style={{
            maxWidth: 460,
            padding: "32px 28px",
            textAlign: "center",
            border: "1px solid #dfe4dc",
            borderRadius: 12,
            background: "#ffffff",
            boxShadow: "0 18px 55px rgba(20, 31, 27, 0.07)"
          }}
        >
          <h1 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 800 }}>Assay hit a fatal error</h1>
          <p style={{ margin: "0 0 16px", color: "#65716a", fontSize: 15, lineHeight: 1.5 }}>
            The application failed to start. Reloading usually clears transient issues.
          </p>
          {error?.message ? (
            <pre
              style={{
                margin: "0 0 16px",
                padding: 12,
                textAlign: "left",
                fontSize: 12,
                whiteSpace: "pre-wrap",
                overflowWrap: "anywhere",
                background: "#f6f8f4",
                border: "1px solid #dfe4dc",
                borderRadius: 8
              }}
            >
              {error.message}
            </pre>
          ) : null}
          <button
            type="button"
            onClick={() => reset()}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 18px",
              border: "1px solid #155e54",
              borderRadius: 8,
              background: "#155e54",
              color: "#ffffff",
              fontWeight: 700,
              cursor: "pointer"
            }}
          >
            Reload
          </button>
        </main>
      </body>
    </html>
  );
}
