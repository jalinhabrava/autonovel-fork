# Descriptor Noise Budget Fixture & Replay Baseline

## Scope

Phase 1.3.K-b1 crea fixture sintético `descriptor_noise_budget`, expected artifacts manuales, replay input congelado manual y tests de harness/replay smoke provider-free. No cambia runtime, schema, viewer, prompts, provider ni write-back.

## Files Changed

- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/source/ch_001.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/source/ch_002.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/source/ch_003.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/fixture_manifest.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/obsidian_import.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/review_queue.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/semantic_invariants_audit.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/replay_input/README.md`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/replay_input/global_normalization.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/replay_input/chapter_outputs/ch_001.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/replay_input/chapter_outputs/ch_002.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/replay_input/chapter_outputs/ch_003.json`
- `tests/test_textifai_descriptor_noise_budget_fixture_harness.py`
- `tests/test_textifai_descriptor_noise_budget_replay_baseline.py`

## Fixture Created

Nuevo fixture:

- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/`

## Fixture Design

Fixture pequeño de 3 capítulos con canonicals sintéticos:

- `Ari Mar`
- `Luma Ser`

Casos cubiertos:

- generic weak descriptor: `el viajero`
- generic multi-chapter without novel facts: `el caminante`
- descriptor with novel facts: `el cartógrafo sin memoria`
- role/title/status descriptor: `el capitán del paso`
- relationship descriptor: `el protector de Luma`
- pronoun-like: `él`
- ephemeral/noise: `mercader distraído`
- duplicate/equivalent descriptors: `el guardián del archivo`, `el custodio del paso`

## Expected Artifacts Created

Artifacts manuales y sintéticos:

- `expected/obsidian_import.json`
- `expected/review_queue.json`
- `expected/semantic_invariants_audit.json`
- `expected/replay_drift_expectations.json`
- `expected/README.md`

No son outputs generados. Son especificación humana para baseline/K-b2.

## Replay Input Created

Replay input manual congelado:

- `replay_input/global_normalization.json`
- `replay_input/chapter_outputs/ch_001.json`
- `replay_input/chapter_outputs/ch_002.json`
- `replay_input/chapter_outputs/ch_003.json`
- `replay_input/README.md`

## Replay Smoke Behavior

- `run_semantic_ingestion_replay(...)` termina OK provider-free con `TemporaryDirectory`.
- Se generan bajo tempdir:
  - `99_System/obsidian_import.json`
  - `99_System/review_queue.json`
  - `99_System/semantic_invariants_audit.json`
- No aparecen:
  - `web_ingestion_job.json`
  - `web_ingestion_job.log`
- No escribe en `runs/**` ni `vault/**`.
- Hashes de replay input no cambian tras el smoke test.

## Descriptor Cases

Reviewables esperados en artifacts manuales:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity`
- `el capitán del paso` -> `review_attach_role_or_title`
- `el protector de Luma` -> `review_enrich_existing_entity`

## Suppressed Cases

Suprimidos/weak por diseño de baseline:

- `el viajero`
- `el caminante` (suppressed o low; no medium por defecto)
- `él`
- `mercader distraído`

## Review Signal Cases

Señales manuales esperadas en `expected/review_queue.json`:

- enrich por facts novedosos
- attach role/title por role descriptor
- enrich por impacto relacional

## Dedupe / Budget Cases

Se documentan surfaces equivalentes para futura observación K-b2:

- `el capitán del paso`
- `el guardián del archivo`
- `el custodio del paso`

K-b1 no endurece aún conteo exacto ni budget run-level. Solo prepara baseline y expectativa de no explosión.

## Language-Agnostic Design

- Manifest y drift expectations explicitan que strings del fixture no son lógica universal.
- Metadata estructural usada en replay input cuando el shape lo permite:
  - `surface_type`
  - `semantic_value`
  - `descriptor_category`
  - `language_hint`
  - `key_facts`
  - `chapter_refs`
  - `source_mentions`
  - `relationships`
- Harness incluye guard prudente para evitar fixture strings en `textifai/vaerl/review_queue.py`.

## Tests Added

- `tests/test_textifai_descriptor_noise_budget_fixture_harness.py`
- `tests/test_textifai_descriptor_noise_budget_replay_baseline.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots` ✅
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals` ✅
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_baseline` ✅
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_contracts` ✅
- `uv run python -m unittest -v tests.test_textifai_object_retention_signal_normalization` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_role_review_signal_decision` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_genericity_policy` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_fixture_harness` ✅
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_baseline` ✅
- `uv run python scripts/textifai.py replay-downstream --help` ✅

## Data Written

- Solo fixtures manuales, replay input manual y tests.
- Replay output solo temporal en validación.

## Safety Constraints

- Sin provider calls.
- Sin ingestión real.
- Sin writes a `runs/**` o `vault/**`.
- Sin schema changes.
- Sin runtime changes.
- Sin viewer changes.
- Sin write-back.

## Known Limitations

- `expected/` es especificación manual, no snapshot generado.
- K-b1 no endurece aún output contracts observados ni drift rules.
- K-b1 no implementa budget run-level real.

## Future Extensions

- `Phase 1.3.K-b2` para replay contracts/drift rules de este fixture.
- posible budget run-level si output observado lo justifica.
- assertions más fuertes sobre dedupe y queue explosion.

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Generated Artifacts: Manual fixtures/replay input only; temp-only replay output

## Provider Calls: NO

## Write-back: NO

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.K-b2 — Descriptor Noise Budget Replay Contracts & Drift Rules`
