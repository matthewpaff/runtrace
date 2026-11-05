# Runtrace

A local agent trace inspection and evaluation workbench. The dashboard combines a run explorer, recorded-event replay cursor, fault injection, deterministic checks, and side-by-side comparison. All bundled data is explicitly synthetic; sample costs are declared fixture values.

## Run

Python 3.10+; no packages, build step, API keys, or network services required.

```powershell
cd runtrace
python server.py
```

Open http://127.0.0.1:8763. The server binds only to loopback. Optional flags: `--port 8763 --db path/to/runs.sqlite3`. A new database receives three synthetic examples. Imports and generated runs persist in SQLite. The database is ignored by version control.

```powershell
python -m unittest discover -s tests -v
```

## What it does

- Generate clean, timeout, rate-limit, and duplicate-delivery scenarios.
- Scrub or play recorded events without reexecuting tools. The evaluator always shows the entire saved run, independently of the cursor.
- Evaluate successful expected evidence, request-scoped consent before side-effect calls, distinct confirmed effect IDs for repeated side-effect request IDs and missing receipt identifiers, tool-call count, and declared cost.
- Compare stable saved summaries. No timestamps, wall-clock durations, or random IDs enter evaluation logic.
- Import JSON traces through a 256 KiB limit and strict structural validation. `sample-trace.json` is a valid example.

## Architecture

`server.py` holds trace validation, fixture simulation, pure evaluation, SQLite persistence, and a small HTTP adapter. `static/` contains a dependency-free responsive dashboard. `tests/test_server.py` exercises event ordering and call/result pairing, budget failures, expected evidence, consent scoping, duplicate-success behavior, persistence, and invalid imports.

HTTP endpoints: `GET /api/health`, `GET /api/runs`, `GET /api/runs/{id}`, `POST /api/simulate`, and `POST /api/import`. Unknown routes and IDs return JSON 404; malformed JSON and invalid trace schemas return JSON 400. Foreign-origin writes are denied. Trace values are rendered with DOM text nodes, never HTML interpolation. Imported tool names and text are inert data; no commands, code, model calls, or external requests are executed.

## Trace contract and adapter seam

A trace has `name`, `scenario`, `synthetic: true`, `budget: {steps, cost}`, `expected` evidence identifiers, and ordered `events`. Event sequence numbers start at one and are contiguous. Kinds are `note`, `consent`, `tool_call`, `tool_result`, `outcome`, and `error`. Every call requires a unique `call_id`, a tool name, and a matching later result. Outcome evidence counts only with `success: true`. Consent grants a recorded `request_id`; side-effect calls reference that same ID. Unknown fields and invalid scalar types are rejected.

A future model adapter could convert structured, redacted application telemetry into this contract and pass it through `validate` then `Store.save`. The current synthetic-only import constraint would require an intentional schema change before accepting real telemetry. Notes are short application annotations, not model reasoning transcripts.

## Limits

This is an inspection lab, not a live LLM integration or production security boundary. Budgets evaluate saved calls and declared dollar costs after a fixture runs; they do not stop an external agent or measure real tokens/billing. The synthetic runner never invokes external tools. Consent and success are assertions in the trace, not independently verified proof. Duplicate detection uses successful results with matching request IDs and distinct effect IDs; identical receipts are treated as idempotent retries. A separate check flags missing receipt identifiers. These remain recorded assertions, not independent proof of external state. Evidence checks match identifiers, not semantic truth. Comparison is descriptive, not a benchmark or statistical performance claim. There is no authentication, multi-user isolation, deletion UI, streaming ingestion, or deployment setup. Keep the server local and use only non-sensitive trace data.

## Demo and review

See [DEMO.md](DEMO.md) for a repeatable walkthrough and the distinction between measured checks and simulated records. See [HISTORY.md](HISTORY.md) for project provenance.
