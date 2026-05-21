# Safe Minimal Fixture Harness

## Scope

Phase 1.3.B created the first committed synthetic fixture harness for future ingestion → VaERL validation work.

Included:

- new synthetic fixture root under `tests/fixtures/textifai/`
- new `minimal_novel` fixture with 3 short source chapters
- human-readable `fixture_manifest.json`
- lightweight existence/safety test
- no runtime, ingestion, replay, VaERL, Obsidian, or schema changes

Excluded:

- no provider calls
- no real ingestion
- no replay execution
- no generated semantic artifacts
- no writes to real `runs/**`
- no writes to real `vault/**`

## Files Changed

- `tests/fixtures/textifai/README.md`
- `tests/fixtures/textifai/minimal_novel/source/chapter_001.md`
- `tests/fixtures/textifai/minimal_novel/source/chapter_002.md`
- `tests/fixtures/textifai/minimal_novel/source/chapter_003.md`
- `tests/fixtures/textifai/minimal_novel/fixture_manifest.json`
- `tests/test_textifai_fixture_harness.py`
- `docs/handoffs/safepoint-023_safe-minimal-fixture-harness.md`

## Fixture Created

Created fixture:

- `minimal_novel`

Properties:

- fully synthetic
- Spanish-only content
- small and reviewable
- no private/user material
- no generated downstream artifacts
- intended as safe committed source fixture only

## Fixture Coverage

Intentional coverage included:

- 2 recurrent characters:
  - Mara Elian
  - Toren
- 1 low-relevance secondary mention:
  - Lio el barquero
- 1 persistent place:
  - Aster Hollow
- 1 persistent object:
  - brújula de plata
- 1 durable relationship:
  - Mara protects Toren
- 1 clear alias case:
  - Mara Elian / Mara
- 1 structural event:
  - escape/juramento toward leaving Aster Hollow
- 1 easy relationship target for later resolution
- 1 episodic mention that should not become important primary entity:
  - guardia cansado

## Manifest Structure

`fixture_manifest.json` stores human expectations, not generated snapshots.

Included fields:

- `fixture_id`
- `title`
- `language`
- `purpose`
- `source_files`
- `intended_coverage`
- `expected_persistent_entities`
- `expected_non_persistent_mentions`
- `expected_relationships`
- `expected_alias_cases`
- `expected_structural_events`
- `notes`

## Tests Added

Added:

- `tests/test_textifai_fixture_harness.py`

Coverage:

- fixture root exists
- manifest exists
- source files exist
- manifest is valid JSON
- manifest `source_files` resolve physically
- language is defined
- persistent entities list is not empty
- relationships list is not empty
- non-persistent mentions field exists
- forbidden generated artifacts are absent
- manifest content does not point to `runs/` or `vault/`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py init --help`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Committed safe data only:

- synthetic Markdown source chapters
- fixture manifest metadata
- fixture README
- test file
- handoff file

No generated semantic artifacts were written.

## Safety Constraints

- synthetic source only
- no user/private material
- no copy from real runs/vaults
- no provider calls
- no ingestion/replay execution
- no writes to `runs/**`
- no writes to `vault/**`
- no artifact snapshots yet

## Known Limitations

- fixture is input-only; it does not yet validate downstream artifact contracts
- no replay baseline harness yet
- no snapshot expectations for `obsidian_import.json`, review queue, or invariants yet
- no semantic edge cases beyond one simple alias and one simple ephemeral mention

## Future Extensions

- add minimal contract snapshots once approved
- add replay-safe temp output harness
- add semantic edge fixture
- add dedicated VaERL fixture
- add Obsidian import fixture

## Semantic Contract Changes: NO

No semantic contract changed.

## Runtime Changes: NO

No runtime behavior changed.

## Generated Artifacts: NO

No generated artifacts were created.

## Provider Calls: NO

No provider call was made.

## Write-back: NO

No write-back behavior changed.

## Next Suggested Phase

Phase 1.3.C — Artifact Contract Snapshot Tests.
