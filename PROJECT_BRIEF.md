# Project Brief — Document Intelligence & Entity Resolution Pipeline

> **Instruction to Claude Code:** Read this brief and generate a `CLAUDE.md` at the repo root.
> Keep `CLAUDE.md` operational and under ~150 lines: what this project is, the invariants you must
> not violate, the layer boundaries, commands to run, and code conventions. Do **not** copy this
> brief verbatim — it contains rationale and roadmap that don't belong in a working context file.
> Roadmap goes in `ROADMAP.md`. Architecture rationale goes in `docs/architecture.md`.

---

## 0. Key concepts, explained

This project sits at the intersection of two things that are each fairly deep on their own. If
you're new to either, here's the short version.

**Document intelligence** is the general practice of taking messy, human-produced documents
(PDFs, scanned pages, HTML) and turning them into structured data a computer can reason about —
e.g. pulling "the contract's effective date is March 1, 2024" out of ten pages of legal prose. The
hard part usually isn't reading the text; it's dealing with inconsistent formatting, scanned
images, tables that don't line up, and documents that don't say things directly.

**Entity resolution** is the harder, less obvious problem this project is really about. Say you
extract a fact from a document: "Acme Corp. signed a lease." Later you extract another fact:
"Acme Corporation renewed its lease." Are those the same company? Legal names get abbreviated,
subsidiaries get folded in, companies get renamed after mergers. Entity resolution is the job of
deciding, across many documents over time, which mentions refer to the same real-world thing —
without either (a) treating the same company as ten different companies, or (b) merging two
different companies into one and quietly corrupting your data. Mistake (b) is called a **false
merge**, and it's the one to fear most, because once two entities' histories are tangled together,
untangling them later is much harder than just not merging them in the first place.

**Reconciliation** is what happens after you know *which* entity a new document is about: does
this new fact agree with what you already believed, update it (a "restatement" — e.g. a company
correcting an earlier filing), or conflict with it (a genuine contradiction that a human should
probably look at)? Reconciliation is how the system keeps a single coherent "current understanding"
per entity instead of just accumulating a pile of disconnected extracted facts.

Most document-extraction projects stop at "read the document, get structured data out." This
project treats that as step one of two. The second step — matching against everything you already
know, and deciding how new information should change that knowledge — is the part that's actually
interesting, and the part most tutorials skip. **If you remember one thing from this brief: getting
data out of a document is the easy half. Deciding what that data means in light of everything else
you already know is the product.**

## 1. What this is

Working name: **Concord** (rename freely).

A pipeline that:
1. Ingests unstructured filings (PDFs, HTML, scanned exhibits).
2. Extracts them into typed, structured schemas (turns prose into fields like `party_name`,
   `effective_date`, `contract_value`).
3. **Resolves** each extraction against everything already known — is this a company we've seen
   before under a different name? Is this fact new, or does it update/contradict something already
   on record?
4. Decides, for each new piece of information: accept it automatically, or flag it for a human to
   review.

**One-sentence thesis:** maintain a trustworthy, auditable state of the world assembled from
untrustworthy documents.

Extraction is the input. **Resolution and reconciliation is the product.** When making design
tradeoffs, favor the resolution layer over extraction convenience.

## 1a. Portfolio scope — the narrow version

The full architecture in this brief (nine layers, multiple sources, MCP, a UI, optional CRM
write-back) is the target shape for where this could eventually go. The portfolio build is a much
narrower slice of it, chosen to prove the thesis end-to-end without extra surface area that
doesn't strengthen the argument:

```
SEC filings -> 1-2 document types -> structured extraction -> entity resolution ->
temporal facts -> reconciliation -> evaluation
```

**The demo:** give Concord ~100 SEC exhibits that reference companies, and show it reconstruct
each company's evolving contractual relationships over time — while flagging the ambiguous or
contradictory cases for human review instead of guessing. The pitch isn't "we extracted data from
documents." It's "we built a system that knows what it doesn't know."

Explicitly cut from the portfolio version — all still legitimate future directions, just not
required to prove the thesis:

- **One source only: SEC EDGAR.** The secondary procurement-portal source mentioned in Section 3
  is a later idea, not part of this build.
- **One or two document types, not "many."** Section 11's roadmap already says this: prove the
  pipeline on one type, add a second only to check that resolution generalizes, then stop. Adding
  a third type doesn't make the demo more convincing; it just costs more labeling time.
- **No CRM write-back.** The optional CRM integration in Section 10 is out of scope.
- **No UI beyond whatever shows the demo running** — a CLI script or notebook that prints the
  before/after state is enough. The "thin read-only view" (Section 4 layer 9, Section 11 phase 7)
  is a stretch goal, not part of the core deliverable.
- **MCP server is a stretch goal, not a requirement.** The demo can be produced by a script that
  calls the pipeline layers directly, in order — no server needed to prove the thesis.

What does **not** get cut, because it's the actual point of the project: the resolution layer
(Section 4, layer 6), the temporal `Fact` model (Section 8/8a), reconciliation — new fact vs.
restatement vs. contradiction (Section 4, layer 7) — and the evaluation harness (Section 9),
especially the false-merge metric. A version of this project without those isn't a narrower
Concord; it's a different, less interesting project.

## 2. Non-goals

State these in `CLAUDE.md`. They exist to prevent scope drift:

- **Not a chat-over-documents app.** This isn't "upload a PDF and ask it questions." No
  RAG-over-a-vector-store as the primary interface — that pattern optimizes for answering
  one-off questions, not for maintaining a structured, auditable record over time.
- **Not a UI project.** Any frontend is a thin, read-only view, and it gets built last, once
  there's something real underneath it to view.
- **Not a general OCR or PDF-manipulation library.** We use OCR/PDF-parsing as a means to an end,
  not as the thing we're building.
- **Not aiming for 100% automation.** Some documents are genuinely ambiguous. Uncertain results
  are supposed to route to a human — that's a feature of the design, not a gap to close later.
- **No scraper anti-bot / evasion work.** We're not building a web-scraping arms-race tool.
  Retrieval targets sources the user has manually pointed us at.

## 3. Corpus (where the documents come from)

Primary source: **SEC EDGAR** — the U.S. Securities and Exchange Commission's public database of
company filings. Specifically, material contracts and exhibits (real MSAs, credit agreements,
leases, amendments).

Why this source: the same companies show up again and again across many filings, but referred to
inconsistently ("Acme Corp." / "Acme Corporation" / "Acme Corp. and its wholly-owned
subsidiaries"). That's exactly the mess that makes entity resolution non-trivial — and worth
building. **Any additional source has to pass a "recurrence test":** pull a sample of 100
documents from it — do the same real-world entities show up 3+ times across that sample, in a
meaningful share of cases? If not, that source doesn't stress-test resolution at all, and adding it
would just turn this back into a plain document extractor. Reject sources that fail this test.

Secondary (optional): state/federal procurement award portals — likely to have similar recurrence
properties, but not required for the initial build. **Cut from the portfolio build entirely** (see
Section 1a) — a second source is a future direction, not something needed to prove the thesis.

## 4. Architecture — nine layers, hard seams

The pipeline is deliberately broken into nine layers, each with a narrow job, connected only to
its immediate neighbors (a layer never reaches past the layer next to it — that's what "hard seams"
means below). This keeps each part independently understandable, testable, and replaceable.

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

A quick walkthrough in plain language:

1. **Retrieval** — fetch the raw document from wherever it lives (a website, an API).
2. **Raw store** — save the original file, untouched, forever. Every document gets a hash (a
   fingerprint of its exact contents) so we can recognize if we've already seen it and skip
   re-processing it.
3. **Classification** — figure out *what kind* of document this is (a lease? a credit agreement?)
   so we know which extraction logic to apply. This step should be cheap/fast — it's just routing.
4. **Extraction** — pull the actual structured fields out of the document. Prefer boring,
   deterministic code (regexes, table parsers) wherever the document format is predictable; use an
   LLM only where the content is genuinely unstructured prose.
5. **Validation** — sanity-check what got extracted. Three tiers, increasingly strict: does it
   match the expected types/schema at all (tier 1)? Does the math/internal logic add up, e.g. do
   line items sum to the stated total (tier 2)? Is it consistent with other documents we already
   have (tier 3)?
6. **Resolution** — the "is this the same entity we've seen before?" step. Explained above in
   Section 0. **Blocking** and **similarity scoring** and **adjudication** are the three stages
   inside this layer — see Section 0 recap and the glossary note below.
7. **Reconciliation** — the "what does this new fact mean for what we already believe?" step. Also
   explained in Section 0.
8. **Review queue** — anything the system isn't confident about doesn't get silently accepted or
   silently dropped — it becomes a queued item a human can look at. This is treated as a real,
   first-class output of the system, not an error state.
9. **Surfaces** — how the outside world interacts with all of the above. Primarily an MCP server
   (a protocol that lets AI tools/assistants call into this pipeline programmatically), plus an
   evaluation harness (Section 9) and, eventually, a simple read-only UI.

**A note on "blocking" and "adjudication" in layer 6 (Resolution):** comparing every new entity
mention against every entity we've ever seen would be far too slow once the record store grows.
**Blocking** is a cheap first pass that narrows the field down to a small set of *plausible*
candidates (e.g. "companies whose name shares a token with this one"). **Similarity scoring** then
ranks those candidates more precisely. Only the genuinely ambiguous cases — where scoring can't
confidently pick a winner — get escalated to **LLM adjudication**, where a model looks at the
actual evidence and makes a judgment call. This three-stage design keeps the expensive step (the
LLM call) rare and reserved for cases that actually need judgment.

Each layer talks to the next only through typed Pydantic models (Python's typed data-validation
library) — never raw dicts, never skipping ahead. **No layer reaches two layers down.** This
constraint is what lets any one layer be rewritten or swapped later without a cascade of changes
elsewhere.

## 5. Invariants (put these in CLAUDE.md verbatim-ish)

These are rules the system must never break, because they're what makes the audit trail — the
ability to answer "why does the system believe this, and where did it come from?" — actually
trustworthy.

1. **Raw documents are immutable.** Never modify or delete a fetched file. If we process a
   document again (say, with an improved extraction method), that creates a *new* extraction
   record — it never overwrites the old one. We keep both, so we can always see what changed.
2. **Every extraction records provenance** — meaning: which source document it came from, which
   page/section if possible, which model and which version of the extraction logic (Skill) produced
   it, when, and how confident it was. Without this, there's no way to later evaluate or debug why
   the system believes something.
3. **Nothing writes to a canonical record without passing validation.** ("Canonical record" =
   the single, current, trusted version of what we believe about an entity.) Anything that fails
   validation, or that the system isn't confident enough about, goes to the review queue instead
   of silently becoming part of the trusted record.
4. **Every resolution decision is persisted with its reasoning and score** — including the
   candidates that were considered and *rejected*, not just the winner. This is what makes
   resolution decisions auditable and reversible later, if a mistake is found.
5. **Deterministic before probabilistic.** "Deterministic" = a fixed set of rules that always gives
   the same answer (a regex, a date parser, a table reader). "Probabilistic" = an LLM call, which is
   more flexible but slower, costlier, and harder to fully verify. Use deterministic methods
   whenever the document format is predictable enough to support them; reserve LLM calls for content
   that's genuinely unstructured.
6. **Content-hash every fetched artifact.** Every document gets a fingerprint of its exact bytes.
   Re-running the pipeline must be *idempotent* (running it twice has the same effect as running it
   once) — an unchanged document should never get re-fetched or re-extracted needlessly.
7. **No LLM calls outside `extraction/` and `resolution/adjudicate.py`.** Every place an LLM can be
   invoked is enumerable and known in advance. This keeps cost, latency, and the surface area that
   needs evaluation bounded and reviewable — you can always answer "where might this be
   non-deterministic?" by looking at exactly two places in the code.

## 6. Stack

- Python 3.11+, async where I/O-bound (`asyncio`, `httpx`); semaphores to cap concurrency
- Pydantic v2 for every inter-layer boundary and every extraction schema
- PostgreSQL + SQLAlchemy + Alembic migrations
- Playwright only where a source requires JS rendering
- Anthropic Python SDK; Claude Skills for per-document-type extraction playbooks
- MCP Python SDK for the server surface
- pytest + fixture corpus of real, ugly documents
- `uv` for dependency management; `ruff` + `mypy` in CI

## 7. Claude Skills layout

A **Claude Skill** here is just a self-contained folder of instructions + supporting code that
tells Claude how to extract one specific document type. One Skill per document type:

```
skills/
  contract-msa/       SKILL.md, schema.py, validators.py, edge-cases.md
  credit-agreement/   SKILL.md, schema.py, validators.py
```

(Two folders shown above — the portfolio build caps at 1-2 document types, per Section 1a. That's
enough to prove resolution generalizes across differently-shaped documents without paying for a
third type's worth of labeling.)

Each `SKILL.md` carries YAML frontmatter (`name`, `description`) and contains: the target schema
(what fields to extract), the extraction playbook (how to extract them), domain validation rules,
and known edge cases. The `description` field is what the system uses to automatically route a
document to the right Skill, so it needs to be precise — vague descriptions cause misrouting.

Why organize it this way: adding a brand-new document type should mean "write a new folder," never
"go modify the core pipeline code." Skills also only get loaded into context when actually needed,
so the rules for a lease don't clutter things up when we're processing a credit agreement.

## 8. Data model sketch

- **Source** — where a document comes from (e.g. "SEC EDGAR").
- **Document** — one raw fetched file: its bytes/blob, its content hash, and fetch metadata.
- **Extraction** — one attempt at pulling structured data out of a Document: the typed payload,
  plus provenance and a confidence score.
- **Entity** — a canonical real-world thing (e.g. one specific company), independent of any single
  document.
- **EntityAlias** — a name variant we've actually observed for an Entity ("Acme Corp.", "Acme
  Corporation", ...).
- **Fact** — one atomic claim about an Entity (e.g. "leased office space starting 2024-03-01"),
  time-scoped, and linked back to the Extraction it came from.
- **ResolutionDecision** — a record of a resolution call: which candidates were considered, their
  scores, the outcome, and who/what made the call (a scoring rule or an LLM adjudicator).
- **ReviewItem** — something queued for a human to look at.
- **EvalRun / EvalResult** — a record of an evaluation run, for tracking accuracy over time.

**Facts are append-only and time-scoped** — meaning we never edit or delete a Fact once it's
recorded; we only add new ones. The canonical Entity record is computed as a *projection* over all
its Facts (i.e., derived by reading through the fact history), not a single row that gets
overwritten in place. This is what makes it possible to reconstruct "what did we believe about
this company as of last March?" later.

### 8a. Entity and Fact, field by field

The most important design choice in this data model: **`Entity` itself stays thin.** It's an
anchor, not a container for the company's current address/status/etc. — that content lives in
`Fact` rows that point back at it. Everything below is a sketch, not code — field names/types will
get pinned down when build phase 4 (Section 11) actually implements this.

**`Entity`** — the canonical anchor:
- `id`
- `entity_type` — e.g. `company`, `person`
- `canonical_name` — a display name for convenience; not itself the source of truth for "the
  correct name," which is derived from `EntityAlias`/`Fact` history
- `external_ids` — e.g. SEC CIK, EIN/LEI, if known. A strong signal during resolution: an exact
  external-ID match is much more trustworthy than a fuzzy name match
- `status` — `active` or `merged_into`
- `merged_into_entity_id` — nullable; set if this Entity was later found to be a duplicate of
  another and merged. Kept as a pointer rather than deleted, so a bad merge is reversible (see
  invariant 4 in Section 5 — resolution decisions must be auditable and reversible)
- `created_at`, `created_from_extraction_id` — provenance for when this Entity first came into
  existence

**`EntityAlias`** — every name variant actually observed for an Entity:
- `id`, `entity_id`
- `alias_text` — the literal string seen ("Acme Corp.", "Acme Corporation", ...)
- `source_extraction_id` — which document/extraction this variant came from
- `first_seen_at`, `last_seen_at`

**`Fact`** — one atomic, time-scoped claim, where the actual content lives:
- `id`, `entity_id`
- `predicate` (a.k.a. `fact_type`) — what kind of claim this is, e.g. `registered_address`,
  `contract_counterparty`, `lease_effective_date`
- `value` — the claim's payload, typed per `predicate`
- `valid_from` / `valid_to` — the time period during which the claim is believed true (this is
  what "time-scoped" means — a Fact about a 2022 address doesn't get erased when a 2024 address
  Fact is added; both persist, each valid for its own period)
- `asserted_at` — when we recorded this Fact (may differ from `valid_from` — e.g. a 2024 filing can
  assert something was true back in 2022)
- `source_extraction_id` — provenance back to the `Extraction` that produced it
- `superseded_by_fact_id` — nullable; points to a later Fact that restates or corrects this one
- `status` — `active`, `restated`, or `contradicted`

**`ResolutionDecision`** — the audit trail for how a mention got linked (or not) to an Entity:
- `id`
- `candidate_entity_ids` and each candidate's similarity score
- `chosen_entity_id` — nullable; unset if the decision was "this is a new Entity"
- `decision_type` — `auto_match`, `new_entity`, `human_confirmed`, or `human_rejected`
- `adjudicator` — which scoring rule, or which LLM (with model id), or which human made the call
- `reasoning`, `confidence`, `created_at`

Concretely: "Acme Corp's current registered address" isn't a column read off one row. It's computed
by taking all `Fact` rows for that `entity_id` with `predicate = registered_address`, filtering out
superseded ones, and picking whichever `valid_from`/`valid_to` window covers "now" (or whatever
date you're asking about).

## 9. Evaluation — non-negotiable

"Evaluation" here means systematically measuring how well the pipeline actually performs, using a
hand-labeled set of correct answers to check against — not just eyeballing a few outputs and
calling it good.

- Hand-labeled golden set (documents where a human has recorded the correct extracted values),
  50+ documents to start, stored in `evals/golden/`.
- The harness reports **per-field precision and recall by document type** — e.g. "for
  credit agreements, we correctly extract `interest_rate` 94% of the time" — never a single
  overall accuracy number, which would hide exactly where the system is weak.
  - *Precision* = of the things we extracted, what fraction were correct.
  - *Recall* = of the things that were actually there to extract, what fraction did we find.
- Also tracks cost (API spend) and latency (time taken) per document, since both matter in
  production, not just correctness.
- Any prompt, Skill, or model change requires a before/after eval run recorded in `evals/runs/` —
  so we can tell whether a change actually helped.
- **Resolution gets its own metrics**, separate from extraction: match precision/recall (did we
  correctly link mentions to the right entity?), plus a **false-merge count** — how many times we
  incorrectly decided two different entities were the same one. A false merge is far more damaging
  than a missed match (failing to link two mentions just means a bit of redundant data; wrongly
  merging two companies corrupts the record), so weight it accordingly when judging whether a
  change is an improvement.

## 10. MCP server surface

**MCP (Model Context Protocol)** is a standard way for AI applications/assistants to call into
external tools and data sources. Exposing this pipeline as an MCP server means any MCP-compatible
client (an AI assistant, another program) can drive it programmatically, without needing a custom
UI or API for each use case.

Planned tools: `ingest_document` · `get_document` · `get_extraction` · `search_entities` ·
`get_entity_timeline` · `resolve_candidates` · `confirm_match` / `reject_match` ·
`list_review_queue` · `run_eval`

Design tools to be composable — small, focused, combinable — rather than one giant "do everything"
tool. Optionally, once the core is stable, consume a CRM's own MCP server to write results back
into it.

**Both the MCP server and CRM write-back are stretch goals, cut from the portfolio build (Section
1a).** The demo doesn't need a server — a script driving the pipeline layers directly is enough to
produce it.

## 11. Build phases (for ROADMAP.md, not CLAUDE.md)

Build in this order — each phase should be genuinely working before starting the next one, so
complexity gets added deliberately rather than all at once. **Per Section 1a, the portfolio build
stops at phase 5** — that's what produces the demo and proves the thesis. Phases 6-7 are stretch
goals, not required to call the build done.

1. One document type, one source (SEC EDGAR), extract → validate → print. No database, no CRM —
   prove the extraction and validation logic first, with the smallest possible moving parts.
2. Label 50 documents by hand. Build the eval harness. **Do this before adding features** — without
   it, you can't tell whether later changes help or hurt.
3. Convert that first type's logic into a proper Skill; add **one more** document type (two
   total — see Section 1a) as a Skill; compare eval numbers between them.
4. Add Postgres, the fact store, and the entity resolution layer — this is where "is this the same
   company?" logic actually gets built.
5. Add the reconciliation policy and the review queue. **Finish line for the portfolio demo:** run
   ~100 SEC exhibits through the full pipeline and produce the demo described in Section 1a —
   reconstructed per-company timelines, plus the ambiguous/contradictory cases sitting in the
   review queue.

Stretch goals, beyond the portfolio build:

6. Build the MCP server.
7. Add a thin, read-only view; optionally, CRM write-back; a third document type or a second
   retrieval source (only if it passes the recurrence test in Section 3).

## 12. Repo conventions

- Layout: `src/concord/{retrieval,storage,classification,extraction,validation,resolution,reconciliation,review,mcp}/`,
  plus `skills/`, `evals/`, `tests/`, `docs/`.
- Full type hints; `mypy` clean.
- Secrets via environment variables only; never commit credentials or API keys. Provide `.env.example`.
- Tests run offline against fixture documents — no network calls in the test suite. (This keeps
  tests fast and reliable, and avoids depending on external sites being up during CI.)
- Commit at every working checkpoint; conventional commit messages.
- README must report real numbers: documents processed, per-field accuracy, cost/latency per
  document, and a running log of what broke and why.

## 13. Tone for CLAUDE.md

Terse and imperative. Prefer "Do X" / "Never Y" over prose. Include a Commands section (install,
migrate, run pipeline, run evals, test, lint) even if the commands are placeholders to be filled in
as the code lands.
