# SP-140 i18n Completion Audit

## Scope
Scanned `textifai/web_viewer/react_shell/src` for remaining hardcoded Arc UI chrome after SP-139.

## Batch plan
1. `App.tsx` safe fallback and display-mapping chrome.
2. Small auxiliary chrome files if still needed after re-audit.
3. Final audit-only pass with deferred ambiguous strings documented.

## Classification
### A. Safe static UI chrome — migrate in this campaign
- `textifai/web_viewer/react_shell/src/App.tsx`
  - relative save-time fallback copy
  - review-item fallback title/summary/evidence copy
  - project-row fallback workspace status copy
  - chapter-content / reanalysis fallback copy

### B. UI-owned display mapping — migrate if display-only
- `textifai/web_viewer/react_shell/src/App.tsx`
  - kind labels for graph chips when UI renders node kind names
  - project fixture labels (`dev fixture`, `real`)

### C. Hydrated/payload/user/canon content — leave raw
- project names, work titles, languages from payload
- chapter titles, entity labels, aliases, evidence excerpts
- review payload recommendation text when backend supplies it
- markdown bodies, canon facts, wikilinks, note paths

### D. Machine/internal value — leave raw
- route IDs, graph node IDs, project IDs, review IDs
- `chapter_id`, `run_id`, `manifest.json`, `.txtfai`
- status-machine values and raw backend messages unless UI-owned fallback

### E. Ambiguous — defer
- Large legacy inspector block inside `textifai/web_viewer/react_shell/src/App.tsx` with mixed payload/chrome content
- Any string requiring layout/className changes to isolate safely

## Current batch: SP-140A
Migrated in this batch:
- `editor.save.not_saved_yet`
- `editor.save.saved_since`
- `editor.no_chapter_content`
- `editor.reanalysis.pending_not_implemented`
- `project.kind.workspace`
- `project.kind.default`
- `project.fixture.dev`
- `project.fixture.real`
- `project.language.pending`
- `project.workspace_status.chapters_detected`
- `project.workspace_status.chapters_ready`
- `project.workspace_status.chapters_failed`
- `project.workspace_status.semantic_review`
- `review.source.candidate`
- `review.source.evidence_pending`
- `review.item.needs_decision`
- `review.item.reviewing_target`
- `review.item.source_with_entity`
- `review.item.no_fragment`
- `graph.kind.chapter`
- `graph.kind.character`
- `graph.kind.concept`
- `graph.kind.event`
- `graph.kind.object`
- `graph.kind.place`
- `graph.kind.review`

## Deferred after SP-140A
- Legacy inspector prose still embedded in `App.tsx`; mixed with payload and would need a separate safe slice.
- Any remaining static chrome in `App.tsx` outside fallback paths after re-audit.

## Acceptance target
No obvious user-facing static fallback chrome should remain hardcoded in migrated `App.tsx` paths above.

## Current batch: SP-140B
Migrated in this batch:
- `graph.edit_draft.readonly`

Scope:
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx` read-only edit draft textarea copy.

Intentional non-translation:
- node label, note path, node kind, and review state stay raw payload/machine values.

## Current batch: SP-140C
Migrated in this batch:
- `review.entity`
- `review.confidence`
- `review.state`
- `review.inspector.label`
- `review.inspector.empty`
- `review.inspector.summary_missing`
- `review.inspector.edit_draft`
- `review.evidence_store`
- `review.yes`
- `review.no`

Scope:
- `textifai/web_viewer/react_shell/src/App.tsx` entity record table and inspector card chrome.

Intentional non-translation:
- entity kind, confidence value, review state, aliases, canonical name, and other payload fields stay raw.

## Current batch: SP-140D
Migrated in this batch:
- `graph.filters_title`
- `graph.view.title`
- `graph.view.subtitle`
- `graph.visible_nodes`
- `graph.edit_title`
- `graph.edit_draft_body`
- `graph.inspector.facts_bio`
- `graph.inspector.main_relations`

Scope:
- `textifai/web_viewer/react_shell/src/App.tsx` legacy graph view chrome and safe legacy inspector labels/buttons.

Intentional non-translation:
- node labels, node IDs, note paths, relationship target/type payload, backlinks, outgoing wikilink labels, and markdown preview stay raw.

## Current batch: SP-140E
Migrated in this batch:
- `project.count.chapters`
- `project.count.nodes`
- `graph.inspector.empty_legacy`
- `graph.inspector.aliases_legacy`
- `graph.inspector.relations_count`
- `graph.inspector.evidence_count`

Scope:
- `textifai/web_viewer/react_shell/src/App.tsx` remaining safe project-row counts and legacy inspector count/empty chrome.

Intentional non-translation:
- heuristic `20 capítulos` scoring string stays raw because it is not rendered UI copy.
- alias values, node labels, IDs, note paths, backlinks, outgoing labels, and markdown preview stay raw.

## Current batch: SP-140F
Migrated in this batch:
- `graph.no_fragment_fallback`
- `codex.title`
- `codex.subtitle`
- `codex.export_selection`
- `codex.view_evidence`
- `codex.story_bible`
- `codex.select_project`
- `graph.select_project`
- `graph.title`
- `graph.route.subtitle`
- `graph.reset_filters`

Scope:
- `textifai/web_viewer/react_shell/src/App.tsx` codex/graph route top-bar and fallback chrome.

Intentional non-translation:
- route IDs, project/entity payload, graph node labels, legacy note content, and backend errors remain raw.
