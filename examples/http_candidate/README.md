# Assay HTTP Candidate Starter

This starter is a local black-box candidate endpoint for Assay. It implements the same HTTP contract used by real agents, so it is useful for testing the full examiner, scoring, persistence, and TraceRazor proof path before wiring a private model or MCP server.

## Run

```powershell
python -m uvicorn examples.http_candidate.server:app --host 127.0.0.1 --port 8080
```

Register it in Assay as:

```text
http://127.0.0.1:8080/ask
```

## Request

```json
{
  "context": "Examiner context and prior lessons",
  "question": "The interview prompt",
  "candidate_id": "cand_example",
  "metadata": { "source": "local-starter" }
}
```

## Response

```json
{
  "answer": "Candidate answer",
  "reasoning": "Short private reasoning summary for trace audit",
  "tool_calls": [],
  "latency_ms": 10,
  "tokens": { "input": 10, "output": 20, "total": 30 }
}
```

Assay stores the full run timeline, then forwards only candidate reasoning and tool steps to TraceRazor.
