import { Suspense } from "react";
import RunDetail from "./RunDetail";

/**
 * Deep-linkable run detail route: `/runs/{runId}`. The drawer + drawer-tab
 * selection live in the URL (`?drawer=trace|spec|research`) via nuqs so a run
 * view is shareable. nuqs reads `useSearchParams` under the hood, which Next
 * requires to be wrapped in <Suspense> on statically-rendered routes.
 */
export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return (
    <Suspense fallback={<RunDetailFallback />}>
      <RunDetail runId={runId} />
    </Suspense>
  );
}

function RunDetailFallback() {
  return (
    <main style={{ padding: 24, color: "var(--color-fg-muted)" }}>
      <p>Loading run…</p>
    </main>
  );
}
