# Architecture rationale

## Thesis

Maintain a trustworthy, auditable state of the world assembled from untrustworthy documents.
Extraction is the input; resolution and reconciliation — deciding whether a document describes a
known entity or a new one, and whether it adds, restates, or contradicts what we already believe —
is the product. Design tradeoffs favor the resolution layer.

## Why SEC EDGAR as the primary corpus

Material contracts and exhibits (MSAs, credit agreements, leases, amendments) have the same
entities recurring across many documents under inconsistent legal names ("Acme Corp." /
"Acme Corporation" / "Acme Corp. and its wholly-owned subsidiaries"). That recurrence is what makes
resolution non-trivial. Any additional source must pass the **recurrence test**: in a 100-document
sample, a meaningful share of entities appear 3+ times. A source that fails this test turns the
project back into a plain extractor — reject it. Secondary/optional source: state/federal
procurement award portals.

## Why nine layers with hard seams

Each layer talks to the next only through typed Pydantic models, and never reaches two layers down.
This keeps extraction, validation, and resolution independently testable and lets the resolution
layer evolve (blocking strategy, scoring model, adjudication policy) without extraction changes
rippling through it, and vice versa.

## Why Claude Skills, one per document type

A Skill is a folder (`SKILL.md` + `schema.py` + `validators.py` + `edge-cases.md`). Skills load on
demand, so per-type extraction rules never all sit in context at once, and adding a new document
type is "write a folder," never "modify the pipeline." `SKILL.md` frontmatter description drives
routing, so it has to be precise.

## Why facts are append-only

`Fact` rows are atomic, time-scoped claims tied to their originating extraction. The canonical
`Entity` record is a projection over facts, not a mutable row — this is what makes resolution
decisions reversible and the audit trail complete. Same reasoning applies to raw documents
(immutable blobs, re-extraction creates a new row) and to `ResolutionDecision` (persisted with
reasoning and score, including rejected candidates).

## Why deterministic-before-probabilistic and LLM-call boundaries

LLM calls are expensive, slower, and harder to eval than deterministic parsing. Restricting them to
`extraction/` and `resolution/adjudicate.py` keeps cost, latency, and eval surface bounded and
reviewable — every LLM call site is enumerable. Regexes, date parsers, and table readers handle
anything with a stable format; LLMs handle genuinely unstructured content only.

## Why eval is non-negotiable

A resolution system with silent false merges is worse than no resolution system — a false merge
corrupts the canonical record in a way that's hard to detect and undo. Per-field precision/recall
by document type (never a single accuracy number), plus resolution-specific match precision/recall
and false-merge count, is how that risk gets caught before it ships. Any prompt/Skill/model change
requires a before/after eval run for the same reason.

## Why MCP as the primary surface

The pipeline is meant to be composed into other tools/workflows, not to be a standalone chat app.
Composable tools (`ingest_document`, `resolve_candidates`, `confirm_match`, etc.) over one mega-tool
keep each capability independently callable and testable. A read-only frontend and CRM write-back
are optional, later additions once the core is stable.
