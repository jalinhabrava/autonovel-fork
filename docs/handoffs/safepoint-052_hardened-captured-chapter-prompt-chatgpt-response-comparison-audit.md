# Hardened Captured Chapter Prompt ChatGPT Response Comparison Audit

## Product Reading

- `safepoint-050` guardó baseline manual de ChatGPT sobre prompt real previo y mostró valor narrativo junto con deuda de contrato.
- `safepoint-051` endureció prompt/schema real con `objects`, `CANONICAL_MAP_MODE`, relaciones en dos capas, `event_importance` y boundaries concept/object/event.
- Esta fase guarda respuesta manual post-`SP-051`, la valida provider-free y la compara contra baseline `SP-050` para comprobar mejora objetiva del contrato.
- No cambia runtime semántico, no llama provider/API, no hace chunking, no hace write-back, merge, promote ni canon mutation.

## Scope

- Guardar sample manual ChatGPT post-`SP-051` para `bootstrap_chapter_extraction` japonés `ch_001`.
- Añadir checklist/schema report provider-free para sample hardened.
- Añadir comparison report vs baseline `SP-050`.
- Añadir issue report actualizado post-hardening.
- Añadir test provider-free dedicado.
- Documentar fase en handoff.

## Files Changed

- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/README.md`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/chatgpt_response_after_sp051_schema_checklist.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/sp050_vs_sp051_response_comparison_report.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/bootstrap_prompt_schema_issue_report_after_sp051.json`
- `tests/test_textifai_real_bootstrap_hardened_chatgpt_response_audit.py`
- `docs/handoffs/safepoint-052_hardened-captured-chapter-prompt-chatgpt-response-comparison-audit.md`

## Hardened Captured Prompt Used

- Prompt source: captura real post-`safepoint-051` del pipeline activo.
- Task: `bootstrap_chapter_extraction`.
- Source file privada: `/home/david/OnT/王者の杖.md`.
- Chapter id: `ch_001`.
- Title detectado: `**（仮）証人**`.
- Language: `ja`.
- `CANONICAL_ENTITY_MAP: []`.
- Contract signals expected in prompt: `chapter_extraction_schema_version: v2`, `objects`, `CANONICAL_MAP_MODE`, `relation_category`, `relation_label`, `event_importance`.

## ChatGPT Response Sample After SP051

- Sample guardado sin alterar semántica, solo como JSON versionado.
- Ruta: `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051.json`.
- No incluye prompt capturado completo ni capítulo fuente completo.
- No representa output runtime real ni canon approval.

## Schema Validation

- JSON parseable.
- Top-level contiene `work` y `chapters`.
- `work.title == "王者の杖"`.
- `work.language == "ja"`.
- Capítulo conserva identidad `ch_001`, título original `**（仮）証人**`, título canónico `（仮）証人`.
- Checklist esperado guardado en fixture versionado.

## V2 Contract Validation

- `chapter_extraction_schema_version == "v2"`.
- `objects` existe y contiene `object_subkind`, `retention_reason`, `needs_review`/`review_state`.
- `events` usa `event_importance` con prioridad `major|supporting|local`.
- `relations` usa `relation_category`, `relation_label`, `relation_summary`, `evidence`.
- Test asegura que relaciones hardened no dependen solo de legacy `relation_type`.

## Useful Coverage

- Cobertura útil retenida para `アデルマン・レオフリック`, `ティセイア王国`, `杖の一族`, `王と杖` / `王者の杖`, `均衡`, `ベル` / `舌のないベル`, `赤子`.
- Eventos útiles retenidos: caída de Thiseia, borrado de `杖の一族`, rescate de `赤子`, transición política de Adelman.
- Review/noise behavior sigue cauteloso para `私`, `赤子`, `王`, `王妃`, `杖`, `後継者`, `お前`.

## Improvements vs SP050

- `ベル` pasa a `objects` y deja de depender de fallback en `concepts`/`unresolved_mentions`.
- Objetos ganan `object_subkind` y `retention_reason`.
- Relaciones ganan dos capas expresivas con evidencia explícita.
- Eventos densos ya no quedan comprimidos a hard cap bajo; sample retiene seis eventos con prioridad.
- `私` y `赤子` siguen en estado review/local candidate, sin falsa canonización.
- Cobertura útil baseline se conserva.

## What Worked Better

- `舌のないベル` queda modelado como `ritual_key` con relación a `赤子` y `私`.
- Labels libres como `rescues_and_raises`, `keeps_artifact`, `maintains_balance_together`, `takes_regency` son más útiles para autor/review.
- `event_importance` distingue eventos mayores de apoyo sin cronología micro-accional.

## What Stayed Weak

- `CANONICAL_ENTITY_MAP` sigue vacío, así que no hay prueba e2e de merge/promote con canon poblado.
- Muestra única japonesa; falta comparar múltiples capítulos.
- Falta auditoría equivalente post-hardening en español.
- Falta comprobar superficies downstream profundas para `objects`.

## Remaining Prompt / Schema Issues

- `empty_canonical_entity_map_in_capture` sigue abierto para e2e real.
- Falta re-audit con canonical map poblado.
- Falta validación multi-capítulo y multilingüe.
- Falta auditoría de chunking/reduction path.
- `relation_label` libre puede producir ruido si downstream lo rigidiza mal.

## Empty Canonical Map Still Open

- Esta fase confirma que hardening guía mejor candidates/review state bajo mapa vacío.
- Esta fase no demuestra comportamiento con mapa parcial o poblado.
- Próxima fase recomendada: audit con canonical map poblado antes de chunking.

## Objects First-class Result

- Resultado positivo: `舌のないベル` aparece en `objects` con `object_subkind: ritual_key` y `retention_reason: event_trigger`.
- Esto resuelve a nivel prompt/schema problema de artefacto persistente sin hogar propio.

## Relation Two-layer Result

- Resultado positivo: sample usa `relation_category`, `relation_label`, `relation_summary`, `evidence`, `facts`, `needs_review`, `review_reason`.
- Mejora expresividad sin crear enum infinito.

## Event Priority Result

- Resultado positivo: sample conserva seis eventos con `event_importance` y sin hard cap rígido de tres.
- `major` y `supporting` aparecen en práctica.

## Provider-free Guarantee

- Ninguna validación hizo llamadas provider/API.
- Ningún archivo contiene secrets.
- Ningún test escribe en `runs/**` o `vault/**`.
- Fase limitada a fixtures, tests, reportes y handoff.

## Tests Added / Updated

- Nuevo: `tests/test_textifai_real_bootstrap_hardened_chatgpt_response_audit.py`.
- Actualizado: `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/README.md`.
- Nuevos expected fixtures para checklist/comparison/issues post-`SP-051`.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_hardened_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_bootstrap_prompt_schema_hardening`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `git status --short`
- `git diff --stat`

## Data Written

- Nuevo sample JSON manual post-`SP-051`.
- Nuevos expected JSON de checklist/comparison/issues.
- Nuevo test audit hardened.
- Nuevo handoff `SP-052`.

## Safety Constraints

- Sin provider calls.
- Sin red usada para datos externos.
- Sin runtime changes.
- Sin chunking.
- Sin write-back.
- Sin commitear prompt capturado completo ni novela fuente completa.

## Known Limitations

- Comparación depende de sample manual ChatGPT, no de provider runtime.
- Evaluación limitada a `ch_001` japonés.
- No prueba populated canonical map ni multi-chapter normalization real.

## Future Extensions

- Audit con canonical map poblado.
- Audit multi-capítulo post-hardening.
- Audit español post-hardening.
- Audit chunking/reduction una vez estable contrato de extracción.
- Revisar surfaces downstream para `objects` y labels libres de relación.

## Runtime Changes

- Ninguno.

## Provider Calls

- No.

## Write-back

- No.

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.M-b5c` — canonical-map populated audit antes de chunking.
