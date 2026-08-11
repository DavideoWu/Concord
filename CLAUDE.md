# Concord — Document Intelligence & Entity Resolution Pipeline

Ingests unstructured filings (PDFs, HTML, scanned exhibits), extracts them into typed schemas, and
resolves them against an existing record store: known entity or new one, new fact or restatement or
contradiction, auto-accept or human review.

**Extraction is the input. Resolution and reconciliation is the product.** When a design tradeoff
pits extraction convenience against resolution correctness, resolution wins.

See `docs/architecture.md` for rationale, `ROADMAP.md` for build phases.

## Iteration 1 scope — build this narrow slice first

The nine-layer, multi-source architecture below is the target shape. Iteration 1 proves the thesis
on a deliberately narrow slice — do not add a second retrieval source, a third document type, an
MCP server, a UI, or CRM write-back until this slice works end-to-end.

- **One source: SEC EDGAR.** No second source until it passes the recurrence test in `docs/architecture.md`.
- **1-2 document types, not more.** Add a second type only to prove resolution generalizes across
  shapes, then stop.
- **No MCP server, no UI, no CRM write-back yet.** Drive layers 1-8 with a script; a server/UI is
  stretch work for later.
- **Finish line:** run ~100 SEC exhibits through retrieval → extraction → resolution →
  reconciliation. Output is per-entity timelines plus a populated review queue for
  ambiguous/contradictory cases — that's the deliverable.
- **Never cut:** resolution (layer 6), the temporal `Fact` model, reconciliation (layer 7), and the
  eval harness. Those are the point of the project, not scope to trim.

See `ROADMAP.md` for the phase-by-phase build order.

## Non-goals

- Not a chat-over-documents app. No RAG-over-a-vector-store as the primary interface.
- Not a UI project. Any frontend is a thin read-only view, built last.
- Not a general OCR or PDF-manipulation library.
- Not aiming for 100% automation. Uncertain results route to human review by design.
- No scraper anti-bot / evasion work. Retrieval targets manually inputted user sources.

## Layers — hard seams

```
1. Retrieval      adapters per source; httpx for static/JSON, Playwright only where JS forces it
2. Raw store      immutable blobs on disk/S3 + content-hash dedup; metadata rows in Postgres
3. Classification cheap document-type classifier -> routes to the right extraction Skill
4. Extraction     per-type Claude Skill + Pydantic schema; deterministic parser where format stable
5. Validation     tier 1 schema/types, tier 2 arithmetic & internal consistency, tier 3 cross-document
6. Resolution     blocking -> similarity scoring -> LLM adjudication only on ambiguous pairs
7. Reconciliation new fact vs. restatement vs. contradiction; conflict policy; canonical record update
8. Review queue   anything below confidence threshold or failing validation; first-class output
9. Surfaces       MCP server (primary), eval harness, thin read view (last)
```

Each layer talks to the next through typed Pydantic models. **Never reach two layers down.**
Layer 9 (Surfaces) is deferred past iteration 1 — see scope note above.

## Invariants — never violate

1. **Raw documents are immutable.** Never modify or delete a fetched blob. Reprocessing creates a
   new extraction row, never overwrites one.
2. **Every extraction records provenance:** source document id, page/span refs where possible,
   model id, prompt/Skill version, timestamp, confidence. No provenance, no eval.
3. **Nothing writes to a canonical record without passing validation.** Failed validation or
   sub-threshold confidence goes to the review queue instead.
4. **Every resolution decision is persisted with its reasoning and score** — including rejected
   candidate matches. Resolution history is auditable and reversible.
5. **Deterministic before probabilistic.** If a field can be parsed with a regex, a date parser, or
   a table reader, do that. LLM calls are for genuinely unstructured content.
6. **Content-hash every fetched artifact.** Re-runs must be idempotent and must not re-extract
   unchanged documents.
7. **No LLM calls outside `extraction/` and `resolution/adjudicate.py`.** Keeps cost, latency, and
   eval surface bounded and reviewable.

## Data model

`Source` · `Document` (raw blob + hash + fetch metadata) · `Extraction` (typed payload + provenance
+ confidence) · `Entity` (canonical) · `EntityAlias` (observed name variants) · `Fact` (atomic claim,
temporal validity, originating extraction) · `ResolutionDecision` (candidates, scores, outcome,
adjudicator) · `ReviewItem` · `EvalRun` / `EvalResult`.

Facts are append-only and time-scoped. The canonical record is a projection over facts, never a
mutable row that gets overwritten.

## Claude Skills

One Skill per document type: `skills/<type>/SKILL.md` (+ `schema.py`, `validators.py`,
`edge-cases.md`). `SKILL.md` frontmatter (`name`, `description`) drives routing — keep the
description precise. Adding a document type is "write a folder," never "modify the pipeline."
Iteration 1 caps this at 1-2 types (see scope note above).

## Stack

- Python 3.11+, async for I/O (`asyncio`, `httpx`), semaphores to cap concurrency
- Pydantic v2 at every inter-layer boundary and every extraction schema
- PostgreSQL + SQLAlchemy + Alembic
- Playwright only where a source requires JS rendering
- Anthropic Python SDK; Claude Skills for per-document-type extraction playbooks
- MCP Python SDK for the server surface
- pytest + fixture corpus of real, ugly documents
- `uv` for dependency management; `ruff` + `mypy` in CI

## Repo layout

```
src/concord/{retrieval,storage,classification,extraction,validation,resolution,reconciliation,review,mcp}/
skills/     one folder per document type
evals/      golden/ (labeled set), runs/ (before/after eval records)
tests/      offline only, fixture documents, no network calls
docs/       architecture.md
```

## Conventions

- Full type hints everywhere; `mypy` clean.
- Secrets via environment variables only. Never commit credentials or keys. Keep `.env.example` current.
- Tests run offline against fixture documents — no network calls in the test suite.
- Commit at every working checkpoint; conventional commit messages.
- README must report real numbers: documents processed, per-field accuracy, cost/latency per
  document, and a running log of what broke and why.

## Evaluation — non-negotiable

- Hand-labeled golden set, 50+ documents to start, in `evals/golden/`.
- Report **per-field precision and recall by document type** — never a single accuracy number.
- Track cost and latency per document.
- Any prompt, Skill, or model change requires a before/after eval run recorded in `evals/runs/`.
- Resolution has its own metrics: match precision/recall, plus false-merge count. A false merge is
  far worse than a missed match — weight accordingly.

## MCP server surface

Stretch goal — not needed until iteration 1's slice (layers 1-8) works end-to-end. Target surface
when it's built:

`ingest_document` · `get_document` · `get_extraction` · `search_entities` · `get_entity_timeline` ·
`resolve_candidates` · `confirm_match` / `reject_match` · `list_review_queue` · `run_eval`

Composable tools, not one mega-tool.

## Commands

```
uv sync                              # install deps
alembic upgrade head                 # run migrations
uv run python -m concord.pipeline    # run pipeline (placeholder)
uv run pytest evals/                 # run evals (placeholder)
uv run pytest                        # run tests
uv run ruff check .                  # lint
uv run mypy src/                     # type check
```
