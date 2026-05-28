# Full Quality Spanish 20ch E2E

## Product Reading
TextifAI depende de calidad semántica. VaERL manda como source of truth. Markdown queda editable para autor. React/Tailwind muestra estado y decisiones.

## Scope
SP-107 ejecuta re-ingestión 20 capítulos con ruta Pro-first. Objetivo: base persistente real para manual-review.

## Files Changed
- `scripts/dev/spanish_20ch_vaerl_markdown_viewer.py`
- `scripts/dev/sp107_full_quality_finalize.py`
- `tests/test_textifai_full_quality_20ch_e2e.py`
- `tests/fixtures/textifai/full_quality_20ch_e2e/expected/*.json`

## User Decision on API Credits
Usuario aprobó gasto API razonable para calidad semántica alta. No estrategia conservadora Flash-first.

## Provider / Model Routing
- provider activo: DeepSeek
- modelo semántico fuerte: `deepseek-v4-pro`
- modelo barato permitido solo no crítico: `deepseek-v4-flash`
- política: low semantic quality escala a fuerte; no repetir retry ciego Flash.

## Source Verification
- source: `/home/david/OnT/ESP 王者の杖 .md`
- size: 836914 bytes
- contenido no expuesto en outputs commit-safe.

## Persistent Run Path
- active run: `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai/runs/sp107_full_quality_pro/20260528T200618Z`
- provider outputs privados bajo `.../provider_runs/...`

## Full 20ch E2E Regeneration
- detección/materialización 20 capítulos completa.
- provider calls reales con `deepseek-v4-pro`.
- reducción válida en 20/20 capítulos.
- write-back de editor: no.

## Chapter Quality Summary
- 20 capítulos detectados.
- 0 listos sin warning.
- 20 listos con warning/revisión semántica.
- 0 retry técnico pendiente.

## Manifest / Status Update
Manifest privado actualizado con:
- `active_run_id`
- `model_routing_summary`
- `status` coherente (ready/review/retry, graph/review readiness).

## Workspace Loader / 8872
- puerto 8872 operativo.
- `/api/projects` lista proyecto persistente y lo marca recomendado.
- mini fixture no queda por defecto.

## Editor / Graph / Review / Story Bible Validation
- Editor: 20 capítulos desde `markdown/Chapters`.
- Graph: nodos/aristas reales del run persistente.
- Review: cola real separada de retry técnico.
- KB markdown (Characters/Places/Events/Objects/Concepts) disponible.

## Quality Comparison
- SP-095 baseline: 445 notes / 445 nodes / 222 edges.
- SP-107: 275 notes / 1971 nodes / 1072 edges.
- diferencia explicada por mayor granularidad de entidades/relaciones del run Pro.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-107_full-quality-20ch-e2e/decision_handoff_private.md`

## Product Decision
`full_quality_20ch_e2e_ready_with_review_warnings`

## Recommended Next Phase
Curación editorial asistida + normalización de warnings semánticos por lote en cola de review.

## What Worked
- Enrutamiento Pro-first ejecutado.
- E2E 20ch completo.
- Base persistente actualizada y cargable por webapp.

## What Failed
- Umbral de scoring interno deja pocos capítulos “ready puro”.
- Persisten warnings semánticos amplios.

## Data Written
- Proyecto persistente privado actualizado.
- Reports commit-safe en `tests/fixtures/textifai/full_quality_20ch_e2e/expected/`.

## Privacy / Non-committed Output
No se commiteó:
- source prose,
- provider raw outputs,
- `/home/david/TextifAIProjects/**`,
- registry local,
- handoff privado.

## Tests Added / Updated
- nuevo: `tests/test_textifai_full_quality_20ch_e2e.py`

## Validation Performed
- preflight provider/model.
- full run Pro-first 20ch.
- packager persistente.
- verificación loader/reader.
- suite unittest relevante.

## Safety Constraints
- sin editor write-back.
- sin merge heuristics.
- sin full project package commit.

## Known Limitations
- scoring heurístico actual castiga capítulos con warnings aunque output útil existe.

## Future Extensions
- mover warnings semánticos a flujos de decisión editorial graduados.
- calibrar score para distinguir mejor “usable with review” vs “retry técnico”.

## Runtime Changes
Se añade script de finalización SP-107 para normalizar estado/reportes.

## Write-back
No editor write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
