# Review-State Candidate Descriptor Signals

## Product Reading

TextifAI no tiene que acertar automáticamente todo el canon. Una entidad puede quedar en review y aun así ser probable primary. Si esa probable primary tiene descriptores, aliases, roles o relaciones relevantes, el autor debe verlo como decisión pendiente. Esta fase no implementa botones ni write-back; solo genera señales editoriales útiles alrededor de entidades en review sin convertirlas en canon.

## Scope

- Runtime mínimo en `textifai/vaerl/review_queue.py`.
- Tests replay provider-free para `descriptor_noise_budget`.
- Drift expectations actualizadas.
- Docs de política de review-state candidates.
- Sin schema change, viewer, provider, prompts, canonicalization broad logic ni write-back.

## Files Changed

- `textifai/vaerl/review_queue.py`
- `tests/test_textifai_review_state_candidate_descriptor_signals.py`
- `tests/test_textifai_descriptor_noise_budget_replay_contracts.py`
- `tests/test_textifai_descriptor_signal_replay_alignment_diagnostics.py`
- `tests/test_textifai_descriptor_genericity_policy.py`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/semantic_edges/descriptor_noise_budget/expected/README.md`
- `docs/operations/retention-review-policy.md`

## Semantic Decision

Un `review_entity` con evidencia suficiente puede actuar como candidate accionable para señales editoriales. Esto no lo convierte en primary/canonical. La decisión humana sigue requerida.

## Runtime Behavior Change

`_absorbed_semantic_surface_items` ahora usa primaries y review-state candidates ponderados. Si una surface descriptor/role/title resuelve contra candidate en review y tiene evidencia suficiente, puede emitir `entity_retention_review` con action editorial.

## Review-State Candidate Policy

Para usar candidate en review:

- no pronoun-like;
- no ephemeral/noise;
- kind durable;
- evidence suficiente por facts/chapter refs/source mentions/relationships;
- surface metadata presente;
- candidate match claro por aliases/source mentions/overlap;
- `do_not_auto_merge: true`;
- `do_not_auto_promote: true`;
- `candidate_requires_review: true`.

## Descriptor Signals Restored

Replay actual emite:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity` sobre `Ari Mar` review-state candidate;
- `el capitán del paso` -> `review_attach_role_or_title` sobre `Ari Mar` review-state candidate;
- `el protector de Luma` -> `review_enrich_existing_entity` compatible relacional sobre `Ari Mar` review-state candidate.

## Suppression Regression

Siguen sin signal fuerte:

- `el viajero`;
- `el caminante`;
- `él`;
- `mercader distraído`.

## No Canon Mutation Guarantee

- `Ari Mar` sigue top-level `review_entity`.
- `primary_count` sigue `0` en el fixture.
- No hay auto-promotion.
- No hay auto-merge.
- No write-back.
- No schema version change.

## Anti-hardcode / Language-Agnostic Guardrails

- Tests estáticos mantienen fixture strings fuera de runtime conditions.
- Test funcional usa surfaces no españolas equivalentes para misma decisión por metadata.
- Runtime decide con `surface_type`, `semantic_value`, `descriptor_category`, evidence, score y candidate state.

## Drift Expectations Updated

Movidos a resolved/current behavior:

- `descriptor_signal_missing_for_novel_facts`;
- `role_descriptor_missing_attach_signal`;
- `relationship_descriptor_missing_impact_signal`;
- `candidate_state_blocks_descriptor_signal`;
- `descriptor_surface_metadata_not_retained`.

Queda drift temporal:

- `descriptor_metadata_incomplete`: el item genérico `review_entity` de `Ari Mar` sigue minimal, pero items descriptor dedicados ya llevan metadata moderna.

## Tests Added / Updated

- Nuevo `tests/test_textifai_review_state_candidate_descriptor_signals.py`.
- Actualizados contratos descriptor noise budget.
- Actualizado diagnóstico K-b3a para estado resuelto.
- Añadido caso unitario en genericity policy para review-state candidate.

## Validation Performed

PASSED:

- `uv run python -m unittest -v tests.test_textifai_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_artifact_contract_snapshots`
- `uv run python -m unittest -v tests.test_textifai_review_queue_retention_signals`
- `uv run python -m unittest -v tests.test_textifai_retention_review_policy`
- `uv run python -m unittest -v tests.test_textifai_replay_expected_drift_rules`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_retention_policy`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_semantic_edge_replay_contracts`
- `uv run python -m unittest -v tests.test_textifai_object_retention_signal_normalization`
- `uv run python -m unittest -v tests.test_textifai_descriptor_role_review_signal_decision`
- `uv run python -m unittest -v tests.test_textifai_descriptor_genericity_policy`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_replay_contracts`
- `uv run python -m unittest -v tests.test_textifai_descriptor_signal_replay_alignment_diagnostics`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_descriptor_signals`
- `uv run python scripts/textifai.py replay-downstream --help`

## Data Written

Only versioned source/test/docs files. Replay artifacts temp-only via `TemporaryDirectory`.

## Safety Constraints

- No provider calls.
- No ingestion real.
- No writes to `runs/**` or `vault/**`.
- No prompt/provider/viewer changes.
- No schema version change.

## Known Limitations

- Role-equivalent surfaces may still generate multiple medium items; full run-level budget remains future work.
- Relationship-specific future action `attach_relationship` not added to avoid viewer vocabulary risk.
- `review_entity` generic metadata remains minimal; descriptor-specific metadata exists on dedicated items.

## Future Extensions

- K-b3c / K-b4: UI action contract for promote/attach/enrich/reject.
- Runtime budget per candidate/category/action if queue grows.
- Optional relationship-specific viewer action vocabulary.

## Semantic Contract Changes

BEHAVIOR ONLY: review queue may emit descriptor/role/enrichment signals for review-state candidates with strong evidence.

## Runtime Changes

YES: `review_queue.py` accepts review-state candidates for absorbed semantic surface review signals.

## Generated Artifacts

Temp-only replay output.

## Provider Calls

NO.

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.K-b3c — Review-State Candidate Noise Budget & Equivalent Descriptor Dedupe`
