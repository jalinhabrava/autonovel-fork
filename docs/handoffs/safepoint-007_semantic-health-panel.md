# Semantic Health Panel

## Scope

- Fase: `Phase 1.1.A — Semantic Health Panel`.
- Objetivo: elevar el viewer a superficie de observabilidad semántica read-only.
- In scope:
  - `textifai/web_viewer/project_reader.py`
  - `textifai/web_viewer/static/app.js`
  - `textifai/web_viewer/static/styles.css`
  - handoff de fase
- Out of scope:
  - `textifai/import_review/**`
  - `textifai/vaerl/**`
  - `textifai/obsidian/**`
  - replay, canonicalization, invariants generation
  - write-back o mutaciones de vault/run

## Files Changed

- `textifai/web_viewer/project_reader.py`
  - agregado summary read-only `health` en payload de `read_project`.
  - agregado cálculo diagnóstico por categorías desde artifacts existentes.
  - sin cambios en contracts semánticos de artifacts fuente.
- `textifai/web_viewer/static/app.js`
  - overview híbrido con panel `Semantic Health`.
  - cards, badges, warnings y secciones expandibles.
  - acceso rápido a `semantic_invariants_audit.json` raw.
- `textifai/web_viewer/static/styles.css`
  - estilos del panel health (status badges, cards, sections, compact table).
- `docs/handoffs/safepoint-007_semantic-health-panel.md`
  - handoff de implementación.

## UI Changes

- `Overview` ahora incluye:
  - badge de estado global (`healthy`, `warning`, `critical`).
  - warnings destacados.
  - grid de categorías:
    - Canon Stability
    - Relationship Integrity
    - Review Pressure
    - Materialization Integrity
  - secciones expandibles:
    - Semantic Invariants (resumen + checks warn/fail + botón raw artifact)
    - Unresolved Targets (resumen rápido)
    - Missing Artifacts (matriz compacta de faltantes)

## Derived Read-Only Metrics

Derivadas únicamente en capa viewer:

- **Canon Stability**
  - `canonical_primary_count`
  - `review_entity_count`
  - `canonical_collision_count` (desde invariants checks)
  - `duplicate_exact_canonical_name_count`
  - `near_duplicate_primary_name_count`
  - `canonical_ambiguity_items` (conteo de review types tipo merge/canonical/alias/identity/duplicate)

- **Relationship Integrity**
  - `relationship_edge_count`
  - `unresolved_relationship_targets` (máximo entre grafo unresolved e invariants `unresolved_relationship_targets.count`)
  - `dangling_relationship_edges`
  - `sample_unresolved_targets`

- **Review Pressure**
  - `review_queue_size`
  - `high_severity_items`
  - `medium_severity_items`
  - `review_type_count`
  - `canonical_ambiguity_items`

- **Materialization Integrity**
  - `missing_expected_artifacts`
  - `missing_expected_artifacts_count`
  - `missing_primary_notes`
  - `missing_review_notes`
  - `missing_chapter_notes`
  - `broken_wikilinks` = `not available` (no inferencia agresiva)

- **Semantic Invariants**
  - `status`, `passed`, `failure_count`, `warning_count`
  - `failing_checks` (solo `warn`/`fail`, con summary corto)
  - `raw_artifact_path`

- **Resumen Global**
  - `overall_status` derivado de invariants/review/unresolved/missing artifacts.
  - `highlights` (máx 6) para diagnóstico rápido.

## Data Sources Used

Solo artifacts ya existentes:

- `semantic_invariants_audit.json`
- `review_queue.json`
- `obsidian_import.json`
- payload `graph` ya derivado por viewer
- metadatos de artifacts presentes en `99_System`

No se generan artifacts nuevos.

## Semantic Contract Risk Analysis

- Riesgo semántico: **bajo**.
- Cambios limitados a agregación y visualización read-only.
- No se modifica:
  - schema de `obsidian_import.json`
  - schema de `review_queue.json`
  - schema de `semantic_invariants_audit.json`
  - lógica de invariants/replay/canonicalization/VaERL.
- Riesgo residual:
  - clasificación visual (`overall_status`) usa reglas simples de observabilidad; no debe interpretarse como nuevo contrato canónico.

## Validation Performed

- Tier 0:
  - `git status --short`
  - `git diff --stat`
  - inspección manual de código viewer
- Tier 1 ligero:
  - `uv run python scripts/textifai.py viewer --help`
  - `uv run python -m unittest -v tests.test_textifai_web_viewer`

No replay. No mutation. No write-back.

## Known Limitations

- `broken_wikilinks` queda en `not available` para evitar heurística invasiva.
- No hay filtros avanzados en sección de invariants/review dentro de health panel (solo resumen inicial).
- No hay comparación entre runs ni diff semántico (fuera de alcance).
- No hay timeline/narrative-state real (fuera de alcance).
- No hay correlación profunda check→entity→chapter (próxima iteración).

## Future Extensions

- Panel dedicado de invariant drill-down con enlaces directos a entities/candidates.
- Upgrade del Review Queue panel (filtros, agrupación, detail drawer).
- Unresolved relationship inspector dedicado.
- Run comparison / semantic diff panel con baselines de fixtures seguras.

## Semantic Contract Changes: NO

- NO

## Runtime Changes: Viewer-only

- YES (solo capa viewer read-only: payload summary + render UI)

## Next Suggested Slice

- `Phase 1.1.B — Review Queue Deep Visibility`
  - filtros por severity/type
  - agrupación por `review_type`
  - detail drawer con evidence/candidates
  - navegación cruzada a graph/artifacts
