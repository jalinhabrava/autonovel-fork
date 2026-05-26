# VaERL Viewer and Retry Classification Audit

## Product Reading
TextifAI combina ingestión semántica VaERL, viewer/manager de VaERL y editor AI interactivo basado en VaERL. SP-087 cerró e2e 20 capítulos con servidor viewer activo, pero revisión manual mostró que el viewer no entrega valor narrativo útil cuando el runtime graph usa etiquetas sintéticas. Esta fase audita gaps y clasifica retry/review sin ejecutar providers.

## Scope
Audit-only. Sin provider calls, sin retry run, sin full-source, sin write-back, sin refactor UI. Solo inventario, comparación, diagnóstico y reportes/privacy-safe + tests.

## Files Changed
- `tests/fixtures/textifai/viewer_audit/expected/*.json`
- `tests/fixtures/textifai/retry_audit/expected/*.json`
- `tests/test_textifai_vaerl_viewer_retry_audit.py`
- `docs/handoffs/safepoint-088_vaerl-viewer-retry-classification-audit.md`

## SP087 Context
- Scope: ch_001–ch_020.
- 41 calls DeepSeek Flash under cap 96.
- 20/20 reductions válidas.
- Writer outcome: 6 ready, 13 needs_retry, 1 needs_review.
- Viewer server: 0.0.0.0:8870 con endpoints 200.
- Private graph runtime: etiquetas sintéticas tipo Character 001.

## TextifAI Product Definition
- Ingestión VaERL: produce conocimiento narrativo real (nombres, relaciones, evidencia).
- Viewer: gestor de conocimiento para autor (Obsidian-like), no panel debug-only.
- Editor AI: debe consumir ese VaERL author-facing.

## Existing Viewer / Obsidian Inventory
Audit confirma rutas existentes:
- `obsidian_import.json` + `review_queue.json` + notas `.md` + tags/wikilinks.
- `project_reader` construye canon/graph/health/canonicalization.
- `app.js` ya soporta graph filters, canon table, review queue, node detail, artifact inspector.
- `ingestion_graph.json` (SP-086) bypass de `build_graph`.

## Previous Graph Detail Capabilities
Ruta previa (obsidian_import) ya mostraba:
- labels canónicos reales;
- aliases, summary, key facts;
- relationships con tipo/facts;
- navegación canon/review;
- note_path + markdown + wikilinks.

## Current Ingestion Graph Projection Audit
SP-087 runtime graph privado:
- existe en `/tmp/.../viewer_project/99_System/ingestion_graph.json`;
- 100/100 labels sintéticas (`Character 001`, etc.);
- edges genéricas (`appears_in`, `happens_at`);
- source refs sí preservadas;
- facts/aliases/evidence no preservados;
- reducción privada sí tenía labels no sintéticas en 20/20 capítulos.
Conclusión: pérdida ocurre en proyección SP-087, no en extracción base.

## Obsidian Import vs Ingestion Graph Gap
`obsidian_import` > `ingestion_graph` actual en valor autor:
- mejor expressiveness, labels reales, aliases, relationships semánticas, conexión con notas.
- `ingestion_graph` actual quedó como metadata sintética útil para smoke técnico, no para autor.

## Node Detail Panel Gap
UI shell actual es reutilizable, pero data insuficiente:
- puede mostrar aliases/facts/relationships/source refs si existen;
- con graph sintético, panel queda pobre.
Falta MVP mínimo de datos reales (canonical_label/surface/aliases/facts/evidence).

## Overview / Writer Outcome Gap
Overview actual depende de contadores legacy (primaries/review queue). En proyectos ingestion_graph-only puede vaciarse/engañar. Debe alinearse con writer outcome real (processed/ready/retry/review/failed + graph counts + CTA).

## Artifacts Role Audit
Artifacts tab vale para debug/dev/export, no UX principal autor. Debe ser superficie secundaria.

## Graph Relationship Quality Audit
Problema principal no es renderer; es proyección:
- edges escasas y genéricas;
- faltan relaciones narrativas útiles (char-char, event-char, object-char, causalidad).

## SP087 Retry Classification Audit
Auditoría capítulo a capítulo (20 filas) indica:
- current: 13 retry, 1 review, 6 ready.
- señales técnicas reales: 20/20 valid+parseable, source refs cubiertas, 1 continuation recuperada.
- failure modes en rerun plan: `low_reduction_score`, `low_objects_count`, `low_relations_count`.
Reclasificación propuesta:
- true technical retry: 0;
- needs_review / ready_with_warnings para mayoría de los 13.

## Retry vs Review Semantics
Definido contrato:
- `needs_retry` solo para fallo técnico/incompleto/invalid/unrecovered.
- `needs_review` para salida válida pero sospechosa o thin.
- `ready_with_warnings` para salida usable con alertas menores.

## Technical-to-User Status Correction Plan
Propuesta:
- quitar regla “low density => retry”.
- mantener retry para fallos técnicos.
- calibrar thresholds por longitud/tipo capítulo.
- añadir tests de mapping técnico→usuario.

## VaERL Viewer Contract Recommendation
Contrato recomendado:
- node: `canonical_label`, `surface_forms`, `aliases`, `facts`, `source_refs`, `evidence_refs`, `note_path`, `backlinks`, `relationships`.
- edge: label semántico real + summary + refs + status/confidence.
- chapter outcome: `ready`, `ready_with_warnings`, `needs_review`, `needs_retry`, `failed`.
Separación explícita:
- core VaERL;
- projection Obsidian-compatible;
- projection viewer;
- debug artifacts.

## Runtime Real Labels vs Fixture Synthetic Labels
Política propuesta:
- runtime/private outputs: labels reales obligatorias.
- synthetic labels: solo fixtures/tests commiteables.
- SP-087 incumplió esto en graph runtime privado.

## General Pipeline Learnings
- Viewer debe operar como KB manager autor-facing.
- Reusar base Obsidian/canon/detail existente.
- Patch clave: proyección VaERL real + mapeo retry/review.

## Provider-specific Learnings
- Mínimo: DeepSeek puede generar low-density válida.
- Viewer/semántica core no debe depender de proveedor.

## Product Decision
`vaerl_viewer_retry_audit_ready_for_patch`

## Recommended Next Phase
Phase 1.3.M-b5c-4r — Patch VaERL projection + retry/review mapping (sin full-source aún).

## What Worked
- Auditoría completa con evidencia de código + SP-087 reports + diagnóstico private packet local.
- Tests nuevos para contratos y reglas de auditoría.

## What Failed
- No se ejecutan cambios runtime/UI en esta fase por política audit-only.

## Data Written
- 12 reports viewer audit.
- 3 reports retry audit.
- Test suite nueva de auditoría.
- Handoff SP-088.

## Privacy / Non-committed Output
- No commit de `/tmp`, prompts/outputs privados, source prose, ni API keys.
- Inspección private packet solo para diagnóstico resumido.

## Tests Added / Updated
- `tests/test_textifai_vaerl_viewer_retry_audit.py`

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_vaerl_viewer_retry_audit`
- `uv run python -m unittest -v tests.test_textifai_viewer_preflight`
- `uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`

## Safety Constraints
Cumplido audit-only: no provider calls, no retry execution, no full-source, no write-back.

## Known Limitations
Clasificación propuesta usa señales disponibles de reportes; falta inspección semántica humana completa capítulo por capítulo con output privado completo.

## Future Extensions
- Patch proyección runtime real-label.
- Patch mapeo retry/review.
- Integrar overview con writer outcome.
- Revalidar viewer manual con datos reales.

## Runtime Changes
Ninguno en esta fase (audit-only).

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
