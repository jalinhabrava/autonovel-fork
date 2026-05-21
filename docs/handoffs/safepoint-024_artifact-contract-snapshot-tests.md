# Artifact Contract Snapshot Tests

## Scope

Phase 1.3.C added synthetic, versioned, manual expected artifacts and contract snapshot tests for `minimal_novel`.

Included:

- expected artifact folder under fixture
- synthetic expected JSON artifacts:
  - `obsidian_import.json`
  - `review_queue.json`
  - `semantic_invariants_audit.json`
- unittest contract checks for shape/fields/safety boundaries
- no runtime changes
- no semantic pipeline execution

Excluded:

- no ingestion execution
- no replay execution
- no provider calls
- no writes to real `runs/**` or `vault/**`
- no changes to extraction/canonicalization/prompts/schemas

## Files Changed

- `tests/fixtures/textifai/minimal_novel/expected/README.md`
- `tests/fixtures/textifai/minimal_novel/expected/obsidian_import.json`
- `tests/fixtures/textifai/minimal_novel/expected/review_queue.json`
- `tests/fixtures/textifai/minimal_novel/expected/semantic_invariants_audit.json`
- `tests/test_textifai_fixture_harness.py`
- `tests/test_textifai_artifact_contract_snapshots.py`
- `docs/handoffs/safepoint-024_artifact-contract-snapshot-tests.md`

## Expected Artifacts Created

Created manual synthetic snapshots:

- `obsidian_import.json`
  - minimal work/chapters/entities set aligned to existing contract fields
- `review_queue.json`
  - minimal actionable queue with `review_entity` and `invariant_*` item examples
- `semantic_invariants_audit.json`
  - minimal audit with `checks` list and `pass_with_warnings` status

## Contract Fields Covered

`obsidian_import` coverage:

- `entities` presence and non-empty
- per-entity critical fields:
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
- slug format safety check
- expected canonical entities present
- alias `Mara` linked to `Mara Elian`
- `guardia cansado` not canonical primary
- chapter refs constrained to stable IDs (`ch_001..ch_003`)

`relationships` coverage:

- list shape
- `target`/`type`/`facts` fields
- relation type set constrained to known synthetic allowed values
- Mara ↔ Toren relation exists

`review_queue` coverage:

- JSON shape and `items` presence
- `review_type`
- `severity` in known set
- source/target/candidates/evidence/metadata fields present

`semantic_invariants_audit` coverage:

- top-level `status` and `checks`
- per-check `name`/`status`/`details`
- status set constrained to `pass|warn|fail|skip`
- at least one passing check

General safety coverage:

- expected directory exists
- JSON files parse
- no references to `runs/` or `vault/`
- no job metadata/log files inside expected snapshot folder
- prior fixture harness now permits manually approved `expected/` snapshots while still forbidding generated artifacts elsewhere in the fixture

## Tests Added

- `tests/test_textifai_artifact_contract_snapshots.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Written data is limited to fixture-side synthetic expected artifacts and test/handoff documentation.

No generated pipeline artifacts were produced.

## Safety Constraints

- no ingestion/replay runtime execution
- no provider calls
- no writes to real `runs/**`
- no writes to real `vault/**`
- no semantic logic edits
- no schema edits

## Known Limitations

- snapshots are manual synthetic contracts, not outputs from a real pipeline run
- relation type validation is constrained to synthetic known set used in this fixture
- no numeric score thresholds or deep semantic quality assertions yet
- no replay baseline execution yet
- `tests/test_textifai_fixture_harness.py` required a narrow compatibility update because Phase 1.3.B intentionally forbade generated artifact names anywhere in the fixture before this approved `expected/` directory existed

## Future Extensions

- add stricter contract checks for additional artifacts once replay-safe harness exists
- add semantic edge fixture expected artifacts
- add drift checks between expected artifacts and future generated fixture outputs
- extend invariant/review queue checks with stronger semantics once baseline policy is approved

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Generated Artifacts: NO

No generated artifacts were produced.

## Provider Calls: NO

No provider call was made.

## Write-back: NO

No write-back behavior changed.

## Next Suggested Phase

Phase 1.3.D — Replay Baseline Harness.
