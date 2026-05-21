# Semantic Edge Fixture for Identity / Alias / Role Retention

## Scope

Crear fixture sintético separado para casos edge de identidad, alias, títulos, roles, descriptores, pronombres y retención, sin tocar runtime ni replay.

## Files Changed

- `tests/fixtures/textifai/README.md`
- `tests/fixtures/textifai/semantic_edges/README.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/source/ch_001.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/source/ch_002.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/source/ch_003.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/fixture_manifest.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/README.md`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/obsidian_import.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/review_queue.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/semantic_invariants_audit.json`
- `tests/fixtures/textifai/semantic_edges/identity_alias_role/expected/replay_drift_expectations.json`
- `tests/test_textifai_semantic_edge_fixture_harness.py`
- `tests/test_textifai_semantic_edge_retention_policy.py`
- `docs/handoffs/safepoint-032_semantic-edge-identity-alias-role-fixture.md`

## Fixture Created

`tests/fixtures/textifai/semantic_edges/identity_alias_role/`

## Fixture Design

- 3 capítulos cortos en español
- entidad canonical `Sera Valen`
- alias `Sera`
- title surface `la princesa`
- descriptor surface `la heredera silenciosa`
- pronoun surface `ella`
- segunda canonical `Ren Tal` con alias `Ren` y descriptor `el muchacho`
- objeto persistente `llave de cristal`
- mención efímera `guardia somnoliento`
- relación estable `alliance` entre Sera Valen y Ren Tal

## Expected Artifacts Created

- `obsidian_import.json`
- `review_queue.json`
- `semantic_invariants_audit.json`
- `replay_drift_expectations.json`
- `README.md`

Todos manuales, sintéticos y versionados.

## Identity / Alias Cases

- `Sera Valen` canonical con alias `Sera`
- `Ren Tal` canonical con alias `Ren`
- aliases quedan en expected artifact, no como primaries separados

## Title / Role / Descriptor Cases

- `la princesa` → review hacia `Sera Valen` con `review_attach_role_or_title`
- `la heredera silenciosa` → review hacia `Sera Valen` con `review_enrich_existing_entity`
- `el muchacho` se documenta como descriptor de `Ren Tal` en manifest, sin promotion automática

## Pronoun Suppression Cases

- `ella` documentada como `pronoun_like`
- no canonical primary
- no strong review signal esperado en artifacts manuales

## Persistent Object Retention Cases

- `llave de cristal` tratada como objeto persistente/durable
- aparece como canonical object en expected artifact
- también queda review item manual de retención accionable con `review_create_primary` y `do_not_auto_merge`

## Ephemeral Mention Cases

- `guardia somnoliento` aparece solo en source fixture
- no canonical primary
- no review fuerte esperado

## Language-Agnostic Design

- fixture escrito en español, pero expectations dependen de metadata estructural
- review items manuales incluyen `surface_type`, `semantic_value`, `candidate_status`, `language_hint`, `do_not_auto_merge`, `future_viewer_actions`
- `language_agnostic_notes` quedan explícitas en manifest y drift expectations

## Tests Added

- `tests/test_textifai_semantic_edge_fixture_harness.py`
- `tests/test_textifai_semantic_edge_retention_policy.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy`
- `git status --short`
- `git diff --stat`

Resultado: PASS en todas las suites ejecutadas.

## Data Written

- source fixture sintético
- expected artifacts manuales
- manifest y README
- tests e handoff

## Safety Constraints

- runtime changes: NO
- schema changes: NO
- provider calls: NO
- replay: NO
- ingestion: NO
- write-back: NO
- runs/vault writes: NO

## Known Limitations

- no hay replay_input todavía
- no se prueba comportamiento runtime real sobre este fixture en esta fase
- expected review queue es manual, no observado desde replay

## Future Extensions

- subfase replay_input congelado
- replay provider-free smoke para este fixture
- drift contracts específicos del semantic edge fixture

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Generated Artifacts: Manual expected artifacts only

## Provider Calls: NO

## Write-back: NO

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.I-b — Semantic Edge Replay Baseline & Drift Contracts.
