# Chapter-scoped Adaptive Retry Pipeline

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. React/Tailwind es cara principal.

## Scope
Añadir soporte real `--chapter-ids`, subchunking chapter-scoped, contrato de outputs/patches, pipeline privado chapter-scoped y piloto controlado de 2 capítulos.

## Files Changed
- `scripts/dev/spanish_20ch_vaerl_markdown_viewer.py`
- `scripts/dev/chapter_scoped_retry_pipeline.py`
- `textifai/import_review/chapter_scoped_retry.py`
- `tests/test_textifai_chapter_scoped_retry_pipeline.py`
- `tests/fixtures/textifai/chapter_scoped_retry_pipeline/expected/*.json`

## SP106D Context
SP-106D diagnosticó que los 13 capítulos fallidos no fallan por parser/schema/provider timeout, sino por `semantic_extraction_low_confidence`.

## High-level --chapter-ids Support
El pipeline alto nivel ahora acepta `--chapter-ids`, valida ids y marca metadata `chapter_scoped`.

## Chapter Subchunking
Se añadió `build_chapter_subchunks` para dividir capítulos en 2-3 partes semánticas preservando source refs.

## Chapter Retry Output Contract
Se añadió contrato `textifai.chapter_retry_result` y patches `chapter_vaerl_patch`, `chapter_graph_patch`, `chapter_review_patch`.

## VaERL / Graph / Review Patch Generation
El pipeline privado genera patches chapter-scoped sin write-back ni integración automática.

## Patch Integration
Integración segura definida pero no aplicada al project package mientras el piloto no supere threshold de calidad.

## Provider Pilot
Piloto controlado sobre `ch_005` y `ch_010` con DeepSeek Flash. Resultado: 4 llamadas, 2 reducciones válidas, 0 capítulos listos, ambos siguen `needs_retry`.

## Workspace Status UX
No se expone jerga técnica en UI. Estado del workspace se mantiene honesto.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-106e_chapter-scoped-retry-pipeline/decision_handoff_private.md`

## Product Decision
Pipeline chapter-scoped queda listo. Piloto no mejora calidad, así que se detiene y no se escala a 13 capítulos.

## Recommended Next Phase
SP-106F: prompt-first split o fallback de modelo para capítulos fallidos, manteniendo chapter-scoped patches.

## What Worked
`--chapter-ids` real, subchunking, contractos de patch, piloto controlado sin full rerun.

## What Failed
DeepSeek Flash con enfoque actual no sacó `ch_005` ni `ch_010` de retry.

## Data Written
Private pilot outputs, private dry patch outputs, reports commit-safe, handoff público.

## Privacy / Non-committed Output
Project package, provider outputs, source prose, registry local y handoff privado no se commitean.

## Tests Added / Updated
`tests/test_textifai_chapter_scoped_retry_pipeline.py`.

## Validation Performed
Ver respuesta final.

## Safety Constraints
No full rerun. No write-back. No raw provider outputs en git. No source prose en reports.

## Known Limitations
Patch integration sigue bloqueada por falta de mejora real en calidad.

## Future Extensions
Fallback a Pro, prompt split por entities/relations/facts, integración incremental real por capítulo.

## Runtime Changes
High-level parser soporta `--chapter-ids`. Nuevo pipeline privado chapter-scoped.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
