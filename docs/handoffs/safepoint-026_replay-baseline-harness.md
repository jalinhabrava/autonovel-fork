# Replay Baseline Harness

## Scope

Phase 1.3.D creó el primer harness seguro para replay downstream desde fixture sintético congelado.

Incluido:

- `replay_input/` manual y versionado para `minimal_novel`
- `global_normalization.json` sintético
- `chapter_outputs/*.json` sintéticos
- test Level 1 de estructura/seguridad del fixture
- test Level 2 smoke provider-free usando `TemporaryDirectory`

Excluido:

- no cambios de runtime
- no cambios de replay logic
- no cambios de schemas
- no cambios de prompts
- no provider calls
- no writes a `runs/**`
- no writes a `vault/**`

## Files Changed

- `tests/fixtures/textifai/minimal_novel/replay_input/README.md`
- `tests/fixtures/textifai/minimal_novel/replay_input/global_normalization.json`
- `tests/fixtures/textifai/minimal_novel/replay_input/chapter_outputs/ch_001.json`
- `tests/fixtures/textifai/minimal_novel/replay_input/chapter_outputs/ch_002.json`
- `tests/fixtures/textifai/minimal_novel/replay_input/chapter_outputs/ch_003.json`
- `tests/test_textifai_replay_baseline_harness.py`
- `docs/handoffs/safepoint-026_replay-baseline-harness.md`

## Replay Input Fixture Created

Created:

- `tests/fixtures/textifai/minimal_novel/replay_input/`

Contents:

- frozen manual `global_normalization.json`
- frozen manual `chapter_outputs/ch_001.json`
- frozen manual `chapter_outputs/ch_002.json`
- frozen manual `chapter_outputs/ch_003.json`
- README explaining safety rules

These files are synthetic fixture inputs, not generated pipeline outputs.

## Fixture Shape

`global_normalization.json` includes:

- `work.title`
- `work.language`
- canonical/global entities:
  - Mara Elian
  - Toren
  - Aster Hollow
  - brújula de plata
  - guardia cansado as low-confidence review entity
- aliases/source mentions
- key facts
- relationships
- chapter refs
- confidence/review state fields

`chapter_outputs/*.json` include:

- one `chapters[0]` payload per file
- `chapter_id`
- title fields
- sequence/label fields
- `chapter_summary`
- characters/places/events/objects
- relations
- unresolved mentions

Coverage:

- Mara Elian / Mara alias
- Toren
- Aster Hollow
- brújula de plata
- Mara ↔ Toren relationship
- `guardia cansado` and `curandera adormilada` as low-persistence signals

## Replay Smoke Behavior

Level 2 smoke is enabled.

Behavior:

- calls `run_semantic_ingestion_replay(...)` directly
- uses `tempfile.TemporaryDirectory`
- patches `get_text_provider` to raise if any provider call is attempted
- passes no auxiliary documents
- validates output root stays inside temp dir
- validates generated temp artifacts exist:
  - `99_System/obsidian_import.json`
  - `99_System/review_queue.json`
  - `99_System/semantic_invariants_audit.json`

No committed generated output is produced.

## Tests Added

- `tests/test_textifai_replay_baseline_harness.py`

Test coverage:

- replay input directory exists
- required JSON files exist
- JSON parses
- fixture files are small
- fixture JSON does not point to `runs/` or `vault/`
- no job metadata/logs in replay input
- provider-free replay smoke writes only into temp output
- expected replay output artifacts appear in temp output

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_replay_baseline_harness`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Committed data:

- synthetic replay input fixture
- replay harness test
- handoff

Runtime test data:

- replay smoke writes generated artifacts only inside `TemporaryDirectory`
- temp output is discarded after test

## Safety Constraints

- no provider calls
- no ingestion real
- no replay CLI writing real paths
- no writes to `runs/**`
- no writes to `vault/**`
- no schema changes
- no runtime changes
- no OnT material

## Known Limitations

- replay input is manually authored, not produced by a real pipeline run
- smoke checks artifact existence and temp-output boundary, not deep semantic equivalence yet
- output artifacts are not snapshotted in this phase
- fixture shape may need expansion before canonicalization/alias quality work

## Future Extensions

- add generated-temp output contract assertions
- compare replay output against `expected/` snapshots where stable
- add semantic edge replay fixture
- add CLI-level replay smoke with explicit temp paths if needed
- add metrics for entity noise and review queue signal quality

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Generated Artifacts: Fixture replay input only

Only manual fixture replay input was committed. Runtime generated artifacts are temp-only.

## Provider Calls: NO

Provider calls are patched to fail in the smoke test; none occurred.

## Write-back: NO

No write-back behavior changed.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.E — Replay Output Contract Assertions.
