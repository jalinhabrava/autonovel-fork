# Canonical Entity Card + Markdown Note Surface + Review Action Model

## Product Reading
TextifAI is author-first. VaERL remains semantic source of truth, Markdown remains editable author substrate, and React/Tailwind remains the main product face.

## Scope
SP-110 adds EntityCardViewModel, entity-card endpoint, graph inspector entity card wiring, author-facing Markdown note rendering, alias classification, review action semantics, discard/materiality contract, and semantic feedback contract.

## Files Changed
- `textifai/web_viewer/entity_card.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/server.py`
- `textifai/web_viewer/react_shell/src/api.ts`
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- `tests/test_textifai_entity_card_review_actions.py`
- `tests/fixtures/textifai/entity_card_review_actions/expected/*.json`

## SP109 Context
SP-109 improved graph inspector, review evidence, dashboard cards, and ingestion progress, but entity cards still relied on partial node/note payloads.

## Entity Card Source Audit
Ren/Sera/Nael now build cards from author graph, VaERL entities/relationships, Markdown, backlinks, outgoing links, review queue, and evidence refs.

## EntityCardViewModel
`textifai.entity_card` returns canonical label, kind, status, summary, alias classification, relationships, counts, backlinks, outgoing links, review state, Markdown author view, and technical metadata.

## Entity Card Endpoint
`/api/projects/<id>/entity-card` accepts `node_id`, `note_path`, or `canonical_label` without breaking `/note`.

## Graph Inspector Entity Card
Graph inspector now accepts rich `entityCardVm` and prefers it over raw node fields.

## Author-facing Markdown Note
Author view hides frontmatter and synthesizes readable sections from VaERL/graph data when note content is technical.

## Edit / Draft Contract
Editing remains read-only/draft affordance. No VaERL or Markdown write-back occurs.

## Alias Classification
Aliases are separated into canonical, contextual/POV, needs_review, and suppressed.

## Review Action Model
Review actions distinguish accept suggested action, reject, manual resolution, create entity, discard from canon, keep as context, view evidence, and defer.

## Review Action Buttons
Generic Fusionar is replaced with contextual labels: Aceptar sugerencia, Elegir otra entidad, Resolver manualmente, Crear entidad nueva, Descartar del canon.

## Manual Resolve Flow
Manual resolve is local-state/UI-contract only; future patch queue can persist it.

## Discard / Materiality Decision
Discard preserves evidence and marks candidate as not canon-worthy without deleting source refs.

## Semantic Feedback Loop Contract
Only project-local learning is default. User/global learning require opt-in. No telemetry implemented.

## Review Dashboard Component
Right panel remains clean dashboard cards; removed local/debug cards.

## Private Decision Handoff
Private handoff path: `docs/handoffs/private/safepoint-110_entity-card-review-actions/decision_handoff_private.md`

## Product Decision
Assessment: `entity_card_ready_review_actions_partial`.

## Recommended Next Phase
Implement persisted draft/patch queue and manual resolve entity picker.

## What Worked
Entity card now fixes relationship counts from graph/VaERL and stops showing frontmatter as primary author content.

## What Failed
Evidence snippets remain limited when no structured evidence text exists.

## Data Written
Commit-safe reports only. No private project package committed.

## Privacy / Non-committed Output
No source prose or raw provider outputs are included in commit-safe reports.

## Tests Added / Updated
Added `tests/test_textifai_entity_card_review_actions.py`.

## Validation Performed
Python unit tests and React build.

## Safety Constraints
No provider calls. No new ingestion. No VaERL write-back. No merge application.

## Known Limitations
Manual resolve is not persisted. Discard is local/UI semantics only.

## Future Extensions
Patch queue, draft persistence, entity picker, source-evidence resolver, and opt-in learning store.

## Runtime Changes
Added entity-card read endpoint and React fetch wiring.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
