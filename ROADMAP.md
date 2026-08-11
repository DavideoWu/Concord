# Roadmap

Build phases for Concord. Each phase should be working and committed before starting the next —
don't add features ahead of schedule.

**Iteration 1 = phases 1-5.** That's the whole portfolio deliverable: one source (SEC EDGAR),
1-2 document types, resolution, temporal facts, reconciliation, and eval — run end-to-end on
~100 SEC exhibits, producing reconstructed per-entity timelines plus a populated review queue for
ambiguous/contradictory cases. Phases 6-7 are stretch goals, not required to call iteration 1 done.

## Iteration 1

1. **One document type, one source, extract → validate → print.** No database, no CRM. Prove the
   extraction schema and validation tiers on real EDGAR contracts.
2. **Label 50 documents. Build the eval harness.** Do this before adding features — per-field
   precision/recall by document type, plus cost and latency per document.
3. **Convert that type's logic into a Skill; add one more document type (two total).** Compare eval
   numbers before/after. Stop at two types — a third doesn't strengthen the demo.
4. **Postgres, fact store, entity resolution layer.** Blocking → similarity scoring → LLM
   adjudication on ambiguous pairs only.
5. **Reconciliation policy + review queue.** New fact vs. restatement vs. contradiction; anything
   sub-threshold or failing validation routes to review. **Finish line:** run ~100 SEC exhibits
   through the full pipeline and produce the demo — per-company evolving contractual relationships,
   with ambiguous/contradictory cases sitting in the review queue instead of being guessed at.

## Stretch (beyond iteration 1)

6. **MCP server.** Composable tools over the pipeline.
7. **Thin read-only view; optional CRM write-back; a third document type or a second retrieval
   source** (only if a source passes the recurrence test in `docs/architecture.md`).
