# Graph Inspector Hydration + Review Evidence UX + Ingestion Progress Polish

## Product Reading
TextifAI is a first-party author platform. VaERL is the semantic source of truth, Markdown is the editable author-facing substrate, and React/Tailwind is the main product surface. The workspace must show useful narrative information instead of technical placeholders.

## Scope
SP-109 improves existing SP-107/SP-108B artifacts without provider calls, new ingestion, retry, write-back, merge application, package changes, screenshots, or browser automation.

## Files Changed
- `textifai/import_review/markdown_graph_index.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/react_shell/src/graph/GraphDataAdapter.ts`
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- `textifai/web_viewer/react_shell/src/graph/types.ts`
- `textifai/web_viewer/static/react-shell/app.css`
- `textifai/web_viewer/static/react-shell/app.js`
- `tests/test_textifai_graph_inspector_review_progress.py`
- `tests/fixtures/textifai/graph_inspector_review_progress/expected/*.json`

## SP108B Context
SP-108B removed dev/run/System contamination from author graph, added `graph/author_graph.json`, hydrated basic ReviewDecisionItem payloads, and added `run_status.json`.

## Graph Inspector Hydration
Backend author graph nodes now expose note-derived `summary_excerpt`, `key_facts_preview`, `relationship_count`, `evidence_count`, `backlinks`, `outgoing_wikilinks`, `display_label`, and `display_kind`. React graph node types and adapter pass these fields to the inspector.

## Canonical Kind Priority
`CANONICAL_KIND_PRIORITY` makes `character > place > object > event > concept > chapter > review > note > unknown > unresolved`. Ren, Sera, and Nael now resolve as `character` when exact canonical labels exist in multiple folders.

## Author-facing Label Cleanup
`format_author_facing_label()` cleans snake_case, camelCase, `unnamed_girl`, `hombre_misterioso`, and pronoun-parenthetical labels like `él (padre de Nael)` for display without changing canonical IDs.

## Review Card Hydration
Review hydration now builds human titles like `X → Y` or `X · sin entidad sugerida`, avoids `review` as subtitle, adds `human_reason`, target/source entities where available, and labels missing targets honestly.

## Evidence Modal Hydration
Backend evidence refs attempt to resolve `char_start`/`char_end` into short local excerpts from chapter Markdown. UI copy treats pointer as technical detail, not primary evidence, and shows an honest missing-fragment state when no excerpt exists.

## Dynamic Review Summary Cards
Backend `decision_summary` remains the source for queue counts. SP-109 improves review copy and local-decision labels; full right-panel dashboard replacement remains partial.

## Review Local State
Accept/Reject/Merge remains local UI state only. No VaERL write-back, merge application, or patch queue persistence is implemented.

## Ingestion Progress Gauges
Ingestion step cards now render progress bars from `run_status.steps`, with Spanish final-state copy and workspace/review CTAs.

## I18N / Copy
Key review buttons and ingestion copy were localized to Spanish: Aceptar, Rechazar, Fusionar, Ver evidencia, Ingesta deshabilitada, Progreso de ingesta.

## Private Decision Handoff
Private details live at `docs/handoffs/private/safepoint-109_graph-inspector-review-progress/decision_handoff_private.md` and must not be staged.

## Product Decision
Assessment: `graph_inspector_ready_review_evidence_partial`.

## Recommended Next Phase
Complete Review side panel dashboard refactor and implement durable local review state / patch queue without applying VaERL write-back automatically.

## What Worked
- Canonical kind priority fixes Ren/Sera/Nael as characters.
- Backend node hydration exposes meaningful inspector fields.
- Review cards have human titles and reasons.
- Evidence refs can include local excerpts when char offsets exist.
- Ingestion screen shows progress bars from run status.

## What Failed
- Full Review right-panel dashboard replacement remains partial because `App.tsx` has dense single-line sections and needs a dedicated component refactor.

## Data Written
- Private project: regenerated `graph/author_graph.json`.
- Commit-safe reports: `tests/fixtures/textifai/graph_inspector_review_progress/expected/*.json`.

## Privacy / Non-committed Output
No project package, source prose, provider outputs, registry, or private handoff are staged or committed.

## Tests Added / Updated
- Added `tests/test_textifai_graph_inspector_review_progress.py`.
- Added nine SP-109 commit-safe reports.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_graph_inspector_review_progress`
- `uv run python -m unittest -v tests.test_textifai_canonical_projection_regression tests.test_textifai_full_quality_20ch_e2e tests.test_textifai_react_workspace_real_project tests.test_textifai_project_package_contract tests.test_textifai_review_workspace_cleanup`
- `cd textifai/web_viewer/react_shell && npm run build`

## Safety Constraints
Provider calls: NO. New ingestion: NO. Full rerun: NO. Write-back: NO. Merge application: NO. Package changes: NO.

## Known Limitations
Review dashboard replacement is partial. Evidence snippets are available only when review refs include usable offsets.

## Future Extensions
- Extract Review dashboard into component.
- Persist local Accept/Reject/Merge state.
- Add patch queue and explicit VaERL write-back.
- Add richer node inspector relationships from VaERL relationships.

## Runtime Changes
Graph API hydrates author graph nodes. Review queue hydration enriches decisions and evidence refs. React bundle rebuilt.

## Write-back
No editor write-back. No VaERL write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
