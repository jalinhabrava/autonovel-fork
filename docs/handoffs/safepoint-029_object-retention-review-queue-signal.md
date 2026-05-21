# Object Retention / Review Queue Signal Decision

## Scope

Phase 1.3.G resolved the first harness-detected omission case by adding an actionable review-queue signal for retained/dropped entities, without promoting them automatically.

Included:

- review queue behavior change for replay/bootstrap generation
- retention review item based on discarded upstream entities
- candidate guess logic for descriptor/title/role cases
- pronoun guardrail
- fixture expectation update for current replay behavior
- new unit/integration tests

Excluded:

- no prompt changes
- no provider changes
- no broad resolver rewrite
- no canonicalization heavy rewrite
- no Obsidian materialization changes
- no write-back actions
- no real `runs/**` or `vault/**` writes

## Files Changed

- `textifai/vaerl/review_queue.py`
- `textifai/import_review/structured_bootstrap_v1.py`
- `tests/test_textifai_replay_expected_drift_rules.py`
- `tests/test_textifai_review_queue_retention_signals.py`
- `tests/fixtures/textifai/minimal_novel/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/minimal_novel/expected/README.md`
- `docs/handoffs/safepoint-029_object-retention-review-queue-signal.md`

## Semantic Decision

Decision implemented:

- do not auto-promote missing persistent entities
- do not auto-merge silently
- do generate actionable review queue signal when durable upstream entity is discarded before `obsidian_import.json`
- do preserve descriptor/title/role information as reviewable semantic signal when there is conservative evidence
- do not treat pronouns as strong primary merge candidates

## Review Queue Signal Added

Added review type:

- `entity_retention_review`

Current behavior:

- `brújula de plata` is still not auto-promoted to primary
- replay output now includes actionable review item for it
- severity defaults to `medium`
- signal includes:
  - `source_entity`
  - `target_text`
  - `candidate_entities`
  - `evidence`
  - `suggested_action`
  - metadata fields:
    - `recommended_action`
    - `do_not_auto_merge`
    - `no_clear_existing_primary`
    - `retention_review_required`
    - `decision_reason`
    - `chapter_refs`

## Candidate Guess / Future Merge Readiness

Added conservative candidate-guess behavior:

- if discarded descriptor/title/role has overlap with existing primary aliases/source mentions, review item can propose candidate primary
- candidate item carries:
  - `canonical_name`
  - `preferred_slug`
  - `entity_kind`
  - `review_state`
  - `reason`
  - `score`
  - `confidence_bucket`

Current object case:

- `brújula de plata` has no clear existing primary merge target
- recommended action becomes `review_create_primary`
- metadata marks `no_clear_existing_primary: true`

## Role / Title / Descriptor Preservation

Guardrail implemented:

- descriptor/title-like discarded entity with candidate evidence generates review signal instead of silent loss
- suggested action for this case:
  - `review_attach_role_or_title`
  - or `review_merge_or_alias` when appropriate
- no automatic canonical mutation occurs

## Data Sources Used

Retention signal currently uses existing upstream data already available in pipeline:

- `promotion_decisions_audit`
- `resolved_entities`
- `global_payload.entities`
- final `obsidian_import`

This avoids schema changes and avoids forcing new runtime persistence layers.

## Tests Added

Added:

- `tests/test_textifai_review_queue_retention_signals.py`

Updated:

- `tests/test_textifai_replay_expected_drift_rules.py`
- fixture drift expectations JSON

Test coverage includes:

- replay object retention review signal for `brújula de plata`
- candidate guess/actionability for descriptor/title case (`la princesa` → `Sera`)
- pronoun guardrail (`ella` never becomes strong primary candidate / no auto-promotion)
- forbidden episodic entities remain non-primary
- queue expectations updated from empty allowed to retention signal expected

## Fixture Expectations Updated

Updated `replay_drift_expectations.json`:

- `brújula de plata` now expects retention signal instead of silent temporary drift acceptance
- `current_empty_queue_allowed` changed to `false`
- queue now expects current retention signal behavior
- optional entity keeps `missing_from_replay_output` state but now requires review handling

## No Aggressive Promotion Guarantee

Validated:

- `brújula de plata` is still not forced into primary output
- `guardia cansado` is not promoted to primary
- `curandera adormilada` is not promoted to primary
- descriptor/title signal does not mutate canonical state

## Descriptor / Pronoun Guardrails

Implemented/tested:

- `la princesa` can produce candidate-based review signal with `Sera`
- `ella` does not become strong primary candidate
- pronoun-like surfaces are suppressed as retention candidates unless future policy changes

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_replay_baseline_harness`
- `uv run python -m unittest -v tests.test_textifai_replay_output_contract_assertions`
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Committed:

- runtime behavior change in review queue generation
- tests
- fixture expectation update
- handoff

Runtime:

- temp-only replay output during tests

## Safety Constraints

- no provider calls
- no real ingestion
- no writes to real `runs/**`
- no writes to real `vault/**`
- no schema version change
- no write-back actions

## Known Limitations

- retention signal currently focuses on discarded upstream entities with enough evidence
- no viewer-side action buttons/write-back yet
- no separate confidence model for candidate guess beyond conservative overlap scoring
- queue may now include event/object retention signals; future policy may refine which durable kinds deserve queue items

## Future Extensions

- decide final product policy for persistent object retention vs secondary mention
- decide whether some retained signals should become `review_keep_secondary` instead of `review_create_primary`
- refine descriptor/title candidate reasoning with richer evidence
- extend same pattern to merge/enrichment review of richer descriptors

## Semantic Contract Changes

BEHAVIOR ONLY

No schema version changed. Review queue generation behavior changed by adding actionable retention-review items.

## Runtime Changes

YES

Review queue generation now incorporates upstream discard context to emit retention/identity review signals.

## Generated Artifacts

Temp-only replay output

## Provider Calls

NO

## Write-back

NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.G2 or 1.3.H — decide product policy for persistent objects: retain as primary, keep secondary, or route through richer review queue signal tiers.
