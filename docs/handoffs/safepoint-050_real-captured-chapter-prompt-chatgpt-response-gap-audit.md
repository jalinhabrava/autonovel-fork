# Real Captured Chapter Prompt ChatGPT Response Gap Audit

## Product Reading

Ya no usamos prompt packet artificial como fuente principal. Se usa prompt real capturado por `safepoint-049` desde pipeline activo (`bootstrap_chapter_extraction`) y respuesta JSON manual de ChatGPT. Esta fase valida parse/schema/cobertura útil y audita límites de prompt/schema sin tocar runtime productivo.

## Scope

- Guardar sample real/manual de ChatGPT para `ch_001` japonés.
- Validar shape y cobertura útil con tests provider-free.
- Registrar gap report y issue report de prompt/schema.
- No tocar runtime semántico, chunking, provider code ni viewer.

## Files Changed

- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/README.md`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/chatgpt_response_schema_checklist.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/chatgpt_response_gap_report.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/bootstrap_prompt_schema_issue_report.json`
- `tests/test_textifai_real_bootstrap_chatgpt_response_audit.py`
- `docs/handoffs/safepoint-050_real-captured-chapter-prompt-chatgpt-response-gap-audit.md`

## Captured Prompt Used

- task: `bootstrap_chapter_extraction`
- source_file: `/home/david/OnT/王者の杖.md`
- chapter_id: `ch_001`
- chapter_title: `**（仮）証人**`
- language: `ja`
- work_title: `王者の杖`
- `CANONICAL_ENTITY_MAP: []`

Nota: prompt completo capturado con texto privado no se commitea en esta fase.

## ChatGPT Response Sample

Sample guardado en:
`tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json`

Se preserva JSON del modelo tal cual (formateado), sin alterar semántica.

## Schema Validation

- JSON parseable.
- Top-level `work` + `chapters` presente.
- `work.title == 王者の杖`, `work.language == ja`.
- Chapter keys requeridas presentes.
- `chapter_id == ch_001`.
- `chapter_title_original == **（仮）証人**`.
- `chapter_title_canonical == （仮）証人`.
- `chapter_label_type` aceptado: `other`/`prologue`.

## Useful Coverage

Coverage útil detectada (match flexible):
- `アデルマン・レオフリック`
- `ティセイア王国`
- `杖の一族`
- `王と杖` / `王者の杖`
- `均衡`
- `ベル` / `舌のないベル`
- `赤子`
- eventos de崩壊/抹消/救出/摂政遷移

## What Worked

- Entidades y conceptos núcleo del prólogo retenidos.
- Eventos macro estructurales retenidos.
- `私` marcado como `pronoun_like` y `needs_review: true`.
- `赤子` mantenido como descriptor con review.
- `ベル` retenido aunque schema fuerza representación como concept/artifact.

## What Was Missing / Weaker

- No `objects` first-class para artifact durable (`ベル`).
- Sin canonical map poblado no puede resolver identidades puente (p.ej. baby→later canon).
- Taxonomía de relations fuerza semántica narrativa fina en tipos genéricos.
- Densidad del prólogo sugiere necesidad de mejor política de priorización/cap de eventos.

## Known Prompt / Schema Issues

Registrados en:
`tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/bootstrap_prompt_schema_issue_report.json`

IDs:
- `empty_canonical_entity_map_in_capture`
- `chapter_schema_missing_objects_section`
- `global_prompt_entire_novel_wording_conflict`
- `relation_type_taxonomy_too_narrow`
- `event_cap_may_be_too_low_for_dense_chapters`
- `chapter_prompt_needs_empty_map_mode`
- `artifact_retention_not_first_class`

## Empty Canonical Map Impact

Sin mapa canónico, el prompt chapter-level hace extracción local útil pero no puede fijar identidades transcapítulo. Debe haber modo explícito de primera pasada con candidatos fuertes + review, sin canon mutation.

## Missing Objects Section Impact

Artifacts persistentes (p.ej. ベル) terminan en `concepts` o `unresolved_mentions`. Esto degrada downstream para ownership/keeper/retention de objetos clave.

## Relation Taxonomy Impact

Relaciones tipo protector/guardian/rescuer/keeper/usurper/survivor_of quedan comprimidas en `dependency`/`uses`/`conflict`. Se pierde precisión editorial.

## Event Cap Impact

Prólogo denso contiene más de 3 eventos durables. Cap rígido o sin tiers puede ocultar hechos clave para revisión.

## Provider-free Guarantee

Tests solo leen archivos JSON/docs locales. No provider/API, no red, no secrets, no write-back.

## Tests Added / Updated

- Añadido: `tests/test_textifai_real_bootstrap_chatgpt_response_audit.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `git status --short`
- `git diff --stat`

## Data Written

Solo fixture/test/docs versionados. Sin prompt privado completo. Sin novela fuente completa.

## Safety Constraints

- No provider calls.
- No network.
- No runtime schema changes.
- No write-back.
- No chunking implementation.

## Known Limitations

- Sample es única respuesta manual ChatGPT; falta comparación multi-run/model.
- No prueba aún capítulo largo con reduction path real + response audit.

## Future Extensions

- Repetir auditoría con canonical map poblado.
- Añadir comparación lado a lado con respuesta de otra LLM/manual run.
- Definir prompt/schema fixes e implementar en fase posterior.

## Runtime Changes

No.

## Provider Calls

No.

## Write-back

No.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.M-b5 — Prompt/Schema Fix Design (objects, empty-map mode, relation taxonomy, event policy) + controlled re-audit before chunking phase.
