# SP-151 Granular ingestion progress

## Backend contract

Ingestion stage payloads now expose:

- `progress_kind`: `determinate` | `indeterminate` | `unavailable`
- `progress`: integer percent when computable
- `completed_units`: completed work units when known
- `total_units`: total work units when known
- `unit_label`: short human label for unit position
- `detail`: short human-readable progress detail

## Semantics

- `determinate` only when total units are known.
- `indeterminate` only when work is running but unit total is not reliable.
- `unavailable` when no reliable progress can be computed.
- Pending stages stay muted; no fake 0% completion.
- Warning and failed stages keep diagnostic state, not fake completion.

## Stage unit mapping

- Chapter detection: chapter count from `chapter_extraction_*` events.
- Markdown writing: chapter count from the same chapter progress timeline.
- Semantic extraction: batch count from `global_normalization_batch_*` events.
- VaERL / graph / review stages remain artifact-driven, not invented from progress events.

## No-fake-progress rule

- Progress snapshot reads JSONL structured events.
- Malformed progress lines are skipped.
- Latest valid event wins.
- Progress events alone do not mark downstream semantic stages complete.
- SP-150A readiness semantics remain intact for structural-only projects.

## Limits

- Not token-level progress.
- No retry or cancel controls in this SP.
- 20-chapter validation stays deferred.

## Known follow-up work

- Normalize stage labels, details, and warnings into one language per flow.
- Make stage ordering truth-preserving so downstream stages do not look active or complete before prerequisites are real.
- Add deeper progress instrumentation for normalization, graph generation, review queue, and validation stages.
- Add chapter-extraction failure recovery and retry handling in a separate SP.
- Add provider/settings warning UI in a separate SP.
- Token-level progress is still out of scope.
