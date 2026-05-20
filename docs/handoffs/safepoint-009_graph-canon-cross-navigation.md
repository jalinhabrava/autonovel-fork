# Graph/Canon Cross-Navigation

## Scope
- Viewer-only, read-only cross-navigation tightening between Review Queue, Canon, and Graph.
- No write-back routes, no semantic artifact mutation, no contract changes.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `docs/handoffs/safepoint-009_graph-canon-cross-navigation.md`

## UI Changes
- Added client-side navigation state for selected canon entity, selected review item, and navigation notices.
- Added `View in graph` actions on canon entity rows with row highlight for selected entity.
- Expanded Review Queue actions with source/target/candidate navigation toward graph and canon.
- Added graph detail actions for `Open in Canon`, `Open Review Context`, and `Open note` when available.
- Added visible feedback banners for successful navigation and `not found` cases.

## Navigation Flows Added
- Review Queue → Graph via source, target, and candidate labels when graph match exists.
- Review Queue → Canon via source, target, and candidate labels when canon match exists.
- Canon → Graph via per-entity inline action.
- Graph → Canon for entity-backed nodes.
- Graph → Review Context for entity/chapter labels when matching review items exist.
- Graph/Canon/Review views now preserve lightweight selection highlights to reduce navigation friction.

## Data Sources Used
- Existing viewer payload only:
  - graph nodes already exposed by viewer backend
  - canon primary/review entities already exposed by viewer backend
  - `review_queue.json` data already exposed by viewer payload
  - note paths already exposed by graph payload

## Semantic Contract Risk Analysis
- Semantic Contract Changes: NO
- Navigation is derived display-only logic in viewer layer.
- No new semantic artifacts were created.
- No source data was normalized, rewritten, merged, or corrected.
- Missing matches now surface explicit UI feedback instead of silent failure.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `uv run python scripts/textifai.py viewer --help`
- `git status --short`
- `git diff --stat`

## Known Limitations
- Matching is name/slug/alias based from already available viewer payload; no new backend resolver was introduced.
- Chapter nodes can open review context if label/id matches queue evidence, but canon navigation remains entity-focused.
- Navigation state is client-side only; there is no URL deep-link contract yet.

## Future Extensions
- Add explicit graph node ↔ review item badges where backend already exposes stable IDs.
- Add raw artifact jump-links for source review items and related invariant failures.
- Add lightweight URL hash/deep-link state if cross-tab sharing becomes useful.

## Semantic Contract Changes: NO
## Runtime Changes: Viewer-only
## Write-back: NO
## Next Suggested Slice
- Phase 1.1.D — Invariant Failure Drilldown with grouped failing checks, related artifacts, and direct navigation into affected entities/review context.
