# Replay Output Contract Assertions

## Scope

Phase 1.3.E added contract assertions over provider-free replay outputs generated from the synthetic `minimal_novel` replay input fixture.

Included:

- new unittest module for replay output contracts
- provider-call fail-fast patch
- temp-only replay output validation
- contract assertions for:
  - `obsidian_import.json`
  - `review_queue.json`
  - `semantic_invariants_audit.json`
  - relationships
  - output boundary
  - fixture immutability

Excluded:

- no runtime changes
- no replay logic changes
- no schema changes
- no canonicalization changes
- no prompt changes
- no writes to real `runs/**`
- no writes to real `vault/**`

## Files Changed

- `tests/test_textifai_replay_output_contract_assertions.py`
- `docs/handoffs/safepoint-027_replay-output-contract-assertions.md`

## Contract Assertions Added

Added replay-output contract test:

- runs `run_semantic_ingestion_replay(...)` from fixture input
- writes only to `TemporaryDirectory`
- loads generated artifacts from temp `99_System`
- checks stable subset contract fields instead of full JSON equality

## Replay Output Fields Covered

`obsidian_import.json`:

- artifact exists and parses
- `entities` non-empty
- each entity includes:
  - `canonical_name`
  - `entity_kind`
  - `preferred_slug`
  - `aliases`
  - `key_facts`
  - `relationships`
  - `chapter_refs`
  - `source_mentions`
  - `confidence`
  - `review_state`
- slug safety via lowercase snake-case-like regex
- chapter refs constrained to `ch_001`, `ch_002`, `ch_003`
- expected core entities detected:
  - Mara Elian
  - Toren
  - Aster Hollow
- alias `Mara` remains associated with Mara Elian
- `guardia cansado`, if present, must not be canonical primary

Observed current replay behavior:

- `brújula de plata` is present in replay input but current downstream replay cleanup does not keep it as a generated primary output for this fixture.
- Test validates current stable output shape instead of forcing runtime changes.

## Relationship Assertions

Checks:

- `relationships` is always a list
- each relationship is a dict
- `target` is present and non-empty
- `type` is present and in fixture-known set:
  - `alliance`
  - `located_in`
  - `related_to`
- `facts` is a list of non-empty strings
- at least one Mara Elian ↔ Toren relationship exists

## Review Queue Assertions

Checks:

- `schema_version == textifai.review_queue.v1`
- `status` is `ready_for_author_review` or `empty`
- `items` is a list
- `item_count` is an int
- empty queue is valid when `item_count == 0`
- if items exist, each item exposes:
  - `review_type`
  - `severity`
  - `source_entity`
  - `target_text`
  - `candidate_entities`
  - `evidence`
  - `metadata`

Observed current replay behavior:

- replay currently produces an empty review queue for this fixture.
- Test treats empty queue as valid contract state, while retaining item-shape assertions for future non-empty outputs.

## Invariant Assertions

Checks:

- `schema_version == textifai.semantic_invariants.v1`
- top-level `status` exists
- `checks` is non-empty list
- each check has:
  - `name`
  - `status`
  - `details`
- check status is one of:
  - `pass`
  - `warn`
  - `fail`
  - `skip`
- at least one passing check exists

## Output Boundary Assertions

Checks:

- replay output is under `TemporaryDirectory`
- result paths resolve under temp output root
- produced paths do not include `/runs/`
- produced paths do not include `/vault/`
- no `web_ingestion_job.json`
- no `web_ingestion_job.log`
- replay fixture input hashes unchanged after test

## Provider Safety

Provider calls are blocked by patching:

- `textifai.import_review.structured_bootstrap_v1.get_text_provider`

The patch raises if replay attempts to call a provider. Test passes only if replay remains provider-free for this fixture.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_replay_baseline_harness`
- `uv run python -m unittest -v tests.test_textifai_replay_output_contract_assertions`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Committed:

- test module
- handoff

Runtime:

- generated replay artifacts only inside `TemporaryDirectory`
- temp artifacts discarded after test

## Safety Constraints

- no ingestion real
- no replay output committed
- no provider calls
- no writes to real `runs/**`
- no writes to real `vault/**`
- no runtime/schema/prompt changes

## Known Limitations

- assertions validate stable contract subset, not full JSON equality
- current replay output drops `brújula de plata` as primary; this is documented, not fixed here
- current replay output queue is empty; non-empty item shape remains covered conditionally
- no comparison against manual expected artifacts yet

## Future Extensions

- add comparison between replay output and manual expected snapshots after deciding acceptable drift rules
- strengthen entity presence once fixture/replay output semantics are tuned
- add semantic edge fixture output assertions
- add review queue signal-quality assertions when fixture produces actionable queue items

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Generated Artifacts: Temp-only replay output

Only temp replay output was generated during tests.

## Provider Calls: NO

No provider call occurred.

## Write-back: NO

No write-back behavior changed.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.F — Replay Expected Drift Rules & Entity Retention Triage.
