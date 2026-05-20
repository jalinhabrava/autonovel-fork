# Canon Drift & Cross-Run Diff Visibility

## Scope
- Phase 1.1.F en viewer: comparación read-only entre dos runs/proyectos.
- Sin write-back, sin replay, sin regenerar artifacts, sin cambios de contratos.
- Solo visualización comparativa y métricas derivadas conservadoras.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `docs/handoffs/safepoint-012_canon-drift-cross-run-diff.md`

## UI Changes
- Nuevo panel `Compare Runs` dentro de Overview.
- Selectores simples para `Base run` y `Candidate run`.
- Resultados agrupados en secciones expandibles para review pressure, invariants, comparability manifest y drift de entidades.
- Labels visuales `improved / worsened / unchanged` limitados a métricas observables.

## Diff Features Added
- Matching conservador de entidades primarias por `entity_kind + preferred_slug`, con fallback implícito a `canonical_name` cuando falta slug.
- Detección de:
  - entities only in base
  - entities only in candidate
  - matched entities with drift
- Drift expandible por entidad matched:
  - canonical name
  - slug
  - kind/subkind
  - confidence
  - aliases added/removed
  - source_mentions added/removed
  - chapter_refs added/removed
  - relationship count delta
  - key facts count delta

## Metrics Compared
- Canon entity stability:
  - matched / only in base / only in candidate / changed matched
- Review pressure:
  - total review items
  - high / medium / low
  - with candidates
  - with evidence
  - review_type counts
- Semantic invariants:
  - status
  - failure_count
  - warning_count
  - failing check names added/removed
  - warning check names added/removed
- Comparability manifest:
  - availability
  - status
  - schema version
  - warnings when present

## Data Sources Used
- Existing viewer project list
- Existing per-project payload from `/api/projects/{id}`
- `obsidian_import.json` via canon payload
- `review_queue.json` via canon payload
- `semantic_invariants_audit.json` via health payload and raw artifact open
- `run_comparability_manifest.json` via read-only artifact fetch when available
- Existing health summaries already exposed by viewer

## Navigation Flows Added
- Open base run
- Open candidate run
- Open base `semantic_invariants_audit.json`
- Open candidate `semantic_invariants_audit.json`
- Open base `run_comparability_manifest.json`
- Open candidate `run_comparability_manifest.json`
- Deep entity navigation kept minimal in this slice; run-level navigation prioritized for simplicity and safety.

## Semantic Contract Risk Analysis
- Semantic Contract Changes: NO
- Runtime Changes: Viewer-only
- Write-back: NO
- Diff is derived and observability-only.
- No new identity inference, no merge suggestions, no artifact mutation.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `node --check textifai/web_viewer/static/app.js`
- `git status --short`
- `git diff --stat`

## Known Limitations
- Matching is intentionally conservative; some semantically same entities may remain unmatched if identifiers drift too much.
- Deep diff navigation opens destination run/artifact, but not per-entity deep-link across runs yet.
- Comparability manifest is optional and may be absent.
- `improved / worsened / unchanged` applies only to observable metrics, not narrative quality truth.

## Future Extensions
- Deep-link per diff row into Canon/Graph for base and candidate.
- Cross-run diff for canonicalization risk signals and nearby review pressure.
- Drift filtering by severity and entity kind.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only
## Write-back: NO
## Next Suggested Slice
- Phase 1.1.G — Entity-Centric Regression Triage (prioritize suspicious entities by combined drift + invariants + review pressure signals).
