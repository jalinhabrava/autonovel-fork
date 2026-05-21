# Replay Expected Drift Rules & Entity Retention Triage

## Scope

Phase 1.3.F added first drift rules for comparing manual expectations against provider-free replay output for `minimal_novel`.

Included:

- manual drift expectations JSON
- unittest rules that run replay in temp dir
- required entity retention checks
- forbidden primary checks
- alias retention checks
- optional entity drift visibility
- review queue expectation checks
- provider/output boundary safety

Excluded:

- no runtime changes
- no replay logic changes
- no cleanup/canonicalization changes
- no prompt changes
- no schema changes
- no writes to real `runs/**` or `vault/**`

## Files Changed

- `tests/fixtures/textifai/minimal_novel/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/minimal_novel/expected/README.md`
- `tests/test_textifai_replay_expected_drift_rules.py`
- `docs/handoffs/safepoint-028_replay-expected-drift-rules.md`

## Drift Expectations Added

Added:

- `tests/fixtures/textifai/minimal_novel/expected/replay_drift_expectations.json`

Sections:

- `required_entities`
- `optional_entities`
- `forbidden_primary_entities`
- `expected_aliases`
- `expected_relationships`
- `known_current_drift`
- `review_queue_expectation`
- `notes`

## Required Entities

Required in current replay output:

- Mara Elian
- Toren
- Aster Hollow

These are currently retained by provider-free replay.

## Optional / Needs Review Entities

Optional but desired:

- brújula de plata

Classification:

- `expected_role`: persistent object
- `current_status`: missing_from_replay_output
- `triage_status`: needs_retention_review

Meaning:

- this does not mark the object as unimportant
- this records current drift pending explicit retention/review-queue decision

## Forbidden Primary Entities

Must not be promoted as important canonical primary:

- guardia cansado
- curandera adormilada

Current replay output does not promote them as primary.

## Known Current Drift

Registered drift:

- `missing_persistent_object_brujula_de_plata`
  - object appears in replay input and manual expected artifacts
  - current replay output omits it as primary
  - accepted temporarily
  - needs retention review
- `empty_review_queue_for_retention_question`
  - replay queue is empty
  - accepted temporarily
  - future phase should decide if object retention question should surface review signal

## Review Queue Expectation

Current policy:

- `current_empty_queue_allowed: true`
- `future_should_surface_retention_question: true`

This keeps the current test green without hiding the drift.

## Tests Added

Added:

- `tests/test_textifai_replay_expected_drift_rules.py`

Tests:

- drift expectation JSON loads and has required sections
- provider-free replay retains required entities
- forbidden primary entities are not promoted
- alias `Mara` remains associated with `Mara Elian`
- optional `brújula de plata` absence is visible and linked to known drift
- empty review queue is accepted only because expectation says so
- outputs remain inside temp dir and no provider call occurs

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_replay_baseline_harness`
- `uv run python -m unittest -v tests.test_textifai_replay_output_contract_assertions`
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Committed:

- drift expectations fixture file
- test module
- README note
- handoff

Runtime:

- temp-only replay output during tests
- discarded automatically

## Safety Constraints

- no provider calls
- no ingestion real
- no replay output committed
- no writes to real `runs/**`
- no writes to real `vault/**`
- no runtime/schema/prompt changes

## Known Limitations

- drift expectations are manual and fixture-specific
- no actual retention behavior changed
- no review queue signal added yet
- no object-retention policy decided yet

## Future Extensions

- decide object retention behavior for persistent objects
- decide whether missing persistent optional entities should create review queue items
- add semantic edge fixture drift rules
- compare output vs manual expected artifacts under explicit drift policy

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Generated Artifacts: Temp-only replay output

Only temp replay output was generated during tests.

## Provider Calls: NO

Provider access remains patched to fail in tests.

## Write-back: NO

No write-back behavior changed.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.G — Object Retention / Review Queue Signal Decision.
