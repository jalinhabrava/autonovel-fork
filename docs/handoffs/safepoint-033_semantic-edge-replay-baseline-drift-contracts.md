# Semantic Edge Replay Baseline & Drift Contracts

## Scope

Añadir replay_input manual congelado para `semantic_edges/identity_alias_role`, ejecutar replay provider-free en temp dir desde tests y registrar contratos/drift observados sin cambiar runtime.

## Files Changed

- `tests/fixtures/textifai/semantic_edges/identity_alias_role/replay_input/README.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/replay_input/global_normalization.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/replay_input/chapter_outputs/ch_001.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/replay_input/chapter_outputs/ch_002.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/replay_input/chapter_outputs/ch_003.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/README.md`
- `tests/test_textifai_semantic_edge_replay_baseline.py`
- `tests/test_textifai_semantic_edge_replay_contracts.py`
- `tests/test_textifai_semantic_edge_fixture_harness.py`
- `docs/handoffs/safepoint-033_semantic-edge-replay-baseline-drift-contracts.md`

## Replay Input Created

Se creó `replay_input/` manual y sintético con:

- `global_normalization.json`
- `chapter_outputs/ch_001.json`
- `chapter_outputs/ch_002.json`
- `chapter_outputs/ch_003.json`
- `README.md`

## Replay Input Shape

- `global_normalization.json` usa shape alineado con `minimal_novel/replay_input`
- incluye entidades/surfaces para `Sera Valen`, `Ren Tal`, `llave de cristal`, `la princesa`, `la heredera silenciosa`, `ella`, `el muchacho`, `guardia somnoliento`
- chapter outputs incluyen `characters`, `objects`, `relations`, `unresolved_mentions` y refs `ch_001/ch_002/ch_003`

## Replay Smoke Behavior

Replay provider-free en temp dir:

- termina OK
- produce `99_System/obsidian_import.json`
- produce `99_System/review_queue.json`
- produce `99_System/semantic_invariants_audit.json`
- no escribe en `runs/**`
- no escribe en `vault/**`
- no muta replay_input

## Output Contract Assertions

Se añadieron assertions sobre:

- shape de `obsidian_import.json`
- shape de `review_queue.json`
- shape de `semantic_invariants_audit.json`
- required entities retenidas
- aliases detectables
- forbidden primaries ausentes
- boundary temp-only
- no provider calls
- drift explícito cuando output observado no coincide con expectation ideal

## Required Entities

No negociable y verificado:

- `Sera Valen`
- `Ren Tal`

Ambas quedan como primaries/canonical output.

## Forbidden Primary Assertions

Verificado:

- `ella` no promoted as primary
- `guardia somnoliento` no promoted as primary
- `la princesa` no primary fuerte
- `la heredera silenciosa` no primary fuerte
- `el muchacho` no primary fuerte

## Review Queue / Actionability Assertions

Observado en runtime actual:

- `la princesa` no genera review signal; queda absorbida como alias/source mention de `Sera Valen`
- `la heredera silenciosa` no genera enrichment signal; queda absorbida como alias/source mention de `Sera Valen`
- `el muchacho` queda absorbido como alias/source mention de `Ren Tal`
- `llave de cristal` no queda primary; queda como `review` entity con item `review_entity` genérico (`merge_into_primary_or_keep_review`) y sin metadata moderna de retención

## Drift Expectations Updated

`expected/replay_drift_expectations.json` ahora separa:

- manual expectation
- current observed behavior
- accepted temporary drift
- non-negotiable failures
- future desired behavior
- language-agnostic notes

## Observed Current Drift

Drift observado y registrado:

- `title_surface_alias_without_review_signal`
- `descriptor_surface_alias_without_enrichment_signal`
- `ren_descriptor_alias_without_review_signal`
- `persistent_object_review_entity_without_retention_metadata`

## Language-Agnostic Design

- fixture sigue en español, pero drift/contract tests no convierten strings del fixture en regla universal
- expectations y notas se apoyan en metadata estructural como `surface_type`, `semantic_value`, `candidate_status`, `language_hint`, `recommended_action`, `future_viewer_actions`
- cuando output actual no preserva metadata nueva, eso se registra como drift explícito

## Tests Added

- `tests/test_textifai_semantic_edge_replay_baseline.py`
- `tests/test_textifai_semantic_edge_replay_contracts.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_contracts`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

Resultado: PASS en todas las suites y checks.

## Data Written

- fixture replay input manual
- drift expectations observadas
- README de replay input
- tests nuevos
- handoff

## Safety Constraints

- runtime changes: NO
- schema changes: NO
- provider calls: NO
- replay output committed: NO
- writes a real runs/vault: NO
- write-back: NO

## Known Limitations

- runtime actual absorbe title/descriptor surfaces como aliases sin review signal específico
- `llave de cristal` aún no produce `entity_retention_review` moderno en este fixture
- metadata estructural moderna de review queue no está presente en output observado para el caso del objeto

## Future Extensions

- fase de decisión sobre role/title/descriptor review visibility
- fase de decisión sobre object retention signal normalizado
- posible tightening de tests cuando runtime mejore y drifts queden resueltos

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Generated Artifacts: Fixture replay input only; temp-only replay output

## Provider Calls: NO

## Write-back: NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.J — Descriptor/Role Review Signal Decision, o fase equivalente para decidir si surfaces absorbidas como alias deben seguir así o deben generar review signal explícito.
