# Review Queue Presentation Grouping

## Product Reading
TextifAI ya genera señales útiles alrededor de entidades en review, ya reduce señales equivalentes para evitar duplicados fuertes y la variante anti-overfitting confirmó que ese comportamiento no depende de nombres o superficies concretas. Esta fase traslada ese valor al viewer: la review queue deja de verse solo como lista plana y pasa a mostrar grupos de decisión editorial. No implementa write-back, merge, promote, edición de canon ni acciones activas.

## Scope
- Añadir agrupación read-only en `textifai/web_viewer/static/app.js`.
- Añadir estilos de grupos y badges en `textifai/web_viewer/static/styles.css`.
- Extender `tests/test_textifai_web_viewer.py` con tests de grouping, fallback legacy y garantías read-only.
- Sin cambios en runtime de review queue, schema, provider o artifacts.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_web_viewer.py`
- `docs/handoffs/safepoint-043_review-queue-presentation-grouping.md`

## Viewer Grouping Added
Se añadió agrupación de presentación sobre items ya existentes del payload de `review_queue.json`.

El viewer ahora puede mostrar:
- grupo editorial de descriptor/rol/título para un candidate concreto;
- grupo de señales equivalentes con principal arriba y related/equivalent debajo;
- grupo separado para object retention;
- fallback legacy/ungrouped para items sin metadata suficiente.

## Grouping Strategy
Agrupación conservadora y read-only basada en metadata existente:
- candidate principal
- `recommended_action` / `suggested_action`
- `descriptor_category`
- `equivalent_signal_group`

Reglas:
- no mezclar candidates distintos;
- no mezclar actions distintas;
- no mezclar descriptor grouping con object retention;
- principal primero;
- related/equivalent visibles debajo;
- items legacy permanecen visibles fuera de grupos modernos.

## Groups Supported
1. `descriptor_group`
   - review-state candidate descriptor / role / title / enrich.
2. `object_retention_group`
   - object retention o create/keep secondary con status de candidate no claro.
3. `legacy / ungrouped`
   - items viejos o sin metadata moderna suficiente.

## Read-only / No Write-back Guarantee
- No se añadieron endpoints POST.
- No hay handlers de write-back.
- No se modifica `review_queue.json`.
- No se toca VaERL, Obsidian ni canon.
- Future actions se muestran como badges/botones deshabilitados solo informativos.

## Legacy Fallback
Los items sin candidate/action/category suficiente siguen renderizando bajo `Legacy / ungrouped review items` sin romper compatibilidad previa.

## Future Actions Presentation
El viewer muestra acciones futuras como presentación read-only:
- `Future action: Attach role/title`
- `Future action: Enrich existing entity`
- `Future action: Keep secondary`
- `Future action: Reject noise`

Además muestra badges de estado:
- `Read-only`
- `Requires human review`
- `No auto-merge`
- `No auto-promote`

## Tests Added / Updated
Actualizados en `tests/test_textifai_web_viewer.py`:
- grouping de medium principal + low equivalentes;
- no mezcla cross-candidate;
- no mezcla cross-action;
- object retention separado;
- fallback legacy/ungrouped;
- future actions siguen disabled/read-only;
- guardas estáticas sin POST/write-back.

## Validation Performed
Ejecutado OK:
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_descriptor_signals`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_noise_budget_dedupe`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_replay_contracts`
- `node --check textifai/web_viewer/static/app.js`
- `uv run python scripts/textifai.py viewer --help`

## Data Written
- Ningún artifact generado.
- Solo cambios en frontend estático, tests y handoff.

## Safety Constraints
- Sin provider calls.
- Sin runtime changes en `textifai/vaerl/review_queue.py`.
- Sin schema changes.
- Sin escritura en `runs/**` o `vault/**`.

## Known Limitations
- Grouping ocurre solo en viewer; payload sigue plano.
- La jerarquía actual es conservadora; no intenta inferir semántica profunda nueva.
- Related items siguen renderizando detalle propio, pero sin acciones activas.

## Future Extensions
- Agrupación visual más rica por candidate + action en viewer.
- Navegación directa entre grupo y contexto de canon/graph.
- Posible resumen plegable por grupo con contadores y filtros específicos.
- Futuro contrato explícito de viewer actions cuando exista write-back real aprobado.

## Semantic Contract Changes
NO

## Runtime Changes
NO

## Generated Artifacts
NO

## Provider Calls
NO

## Write-back
NO

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.L-c — Review Queue Viewer Group Summaries & Navigation Polish.
