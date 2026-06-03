# SP-126A Hardcoded UI String Audit

## Scope
Scanned `textifai/web_viewer/react_shell/src` for user-visible string literals and i18n gaps.

## Files scanned
- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/common/ui.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
- `textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx`
- `textifai/web_viewer/react_shell/src/modules/editor/EditorView.tsx`
- `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx`
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx`
- `textifai/web_viewer/react_shell/src/modules/review/ReviewQueueView.tsx`
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx`
- `textifai/web_viewer/react_shell/src/shell/navigation.ts`
- `textifai/web_viewer/react_shell/src/i18n/ui.ts`

## Top hardcoded-string hotspots
- `textifai/web_viewer/react_shell/src/i18n/ui.ts` — current catalog plus locale foundation.
- `textifai/web_viewer/react_shell/src/App.tsx` — overview cards and several shell labels still hardcoded.
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx` — inspector chrome and fiche controls still contain raw copy.
- `textifai/web_viewer/react_shell/src/modules/*` — feature panels already use `t(...)` in many places, but some label text still lives inline.
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx` — shell chrome now uses i18n keys for local-first / project-status labels.

## Categories
### A. User-visible text that must become i18n
- Shell chrome labels, status chips, user menu labels, overview cards, navigation labels, action buttons, placeholders, and help copy.
- Remaining hardcoded text in `App.tsx` overview copy.
- Remaining graph/editor/review feature labels not already wired through `t(...)`.

### B. Safe internal/machine strings that must remain as-is
- Route IDs, section IDs, graph node IDs, review state machine values, API payload keys, project IDs, file paths, and VaERL schema fields.
- Technical tokens such as `manifest.json`, `.txtfai`, `run_id`, `editorKey`, `chapter_id`, and storage keys when used as machine identifiers.

### C. Test-only strings
- Fixture names and expectation labels under `tests/fixtures/textifai/i18n/expected/`.
- Audit assertions in `tests/test_textifai_i18n_ui_strings.py`.

### D. Ambiguous strings needing review
- Labels that look like product copy but may encode product concepts: `Canon`, `VaERL`, `Project Hub`, `AI Studio`, `Story Bible`.
- Strings that may be safe labels in UI but could be mistaken for internal tokens when they match machine-like names.

## Recommended migration order
1. Shell / navigation / top-bar chrome.
2. Overview board copy in `App.tsx`.
3. Graph inspector and graph toolbar labels.
4. Review queue and project hub labels.
5. Editor and deeper feature chrome.

## Risky strings not to translate
- `manifest.json`
- `.txtfai`
- `run_id`
- route/view IDs like `hub`, `ingest`, `review`, `graph`, `codex`, `editor`, `ask`, `overview`
- entity names, aliases, chapter titles, project names, graph node labels, and any VaERL schema keys

## Notes
- Existing i18n catalog already spans `en` and `es`.
- SP-126A added locale-resolution foundation and shell-key aliases; deeper feature migration remains for later safepoints.

## SP-126B Progress Note
- App overview/workspace copy in `textifai/web_viewer/react_shell/src/App.tsx` migrated to i18n.
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx` deferred because file had pre-existing dirty style/token changes before SP-126B started.
- Remaining hotspots: `ProjectHubView.tsx`, `GraphInspector.tsx`, `CanonVaerlView.tsx`, `EditorView.tsx`, `ReviewQueueView.tsx`, `IngestionView.tsx`, `AIStudioView.tsx`.

## SP-126C Dirty-File Triage

SP-126B commit `33da88df462e5fa407bd0edd9f87bd0c334e3281` is present on `origin/phase-1.4-authoring-workbench-projectstore`; no SP-126B push was required before triage.

No additional i18n slice was migrated in SP-126C. All preferred target files were dirty before SP-126C or tied to graph palette/style diffs, so migrating any one of them would mix i18n with unrelated visual or semantic-color work.

| File | Dirty before SP-126C | Diff nature | Recommendation |
| --- | --- | --- | --- |
| `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx` | yes | graph palette/style extraction | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/graph/GraphTheme.ts` | yes | graph semantic color indirection | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx` | yes | graph chip palette/style changes; copy already uses `t(...)` | migrated in SP-133 as i18n-key-only cleanup; no style or graph-behavior changes |
| `textifai/web_viewer/react_shell/src/graph/GraphPalette.ts` | yes, untracked | new graph palette constants | do not touch in SP-126C |
| `textifai/web_viewer/react_shell/src/modules/ai/AIStudioView.tsx` | yes | style/token class changes; visible copy already uses `t(...)` | defer |
| `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx` | yes | style/token class changes; visible copy already uses `t(...)`; machine status remains raw | defer |
| `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx` | yes | style/token class changes plus one existing Spanish note | defer |
| `textifai/web_viewer/react_shell/src/modules/canon/CanonVaerlView.tsx` | yes | style/token class changes in canon-sensitive module | defer |
| `textifai/web_viewer/react_shell/src/modules/canon/StoryAliasView.tsx` | yes | style/token class changes in canon-sensitive module | defer |

Deferred hotspots for later clean safepoints:

- `ProjectHubView.tsx` — migrate remaining user-facing note after style/token diff is resolved; keep `manifest.json` and `.txtfai` raw.
- `GraphInspector.tsx` — schedule as dedicated graph/canon i18n slice because inspector labels are larger and entity-sensitive.
- `CanonVaerlView.tsx` and `StoryAliasView.tsx` — schedule after canon module style diffs are clean.
- `AIStudioView.tsx` and `IngestionView.tsx` — revisit after style diffs are resolved; current visible copy already routes through i18n keys except machine/runtime values.

Assessment: `arc_i18n_dirty_worktree_triage_ready`.

## SP-128 ProjectHubView Micro-Slice

SP-128 migrated one safe ProjectHubView i18n micro-slice without expanding into broader UI-string cleanup.

Migrated keys:

- `project.manifest_name`
- `project.contract_note`

Migrated strings:

- `manifest.json` now renders through `project.manifest_name` in the contract metric.
- `Un archivo abre el bundle completo.` now renders through `project.contract_note` in the contract metric.

Remaining `ProjectHubView.tsx` hardcoded strings:

- `.txtfai` remains inline as an intentional machine/package-format token, matching the existing risky-strings guidance in this audit.
- No remaining Spanish or English prose literals were found in `ProjectHubView.tsx` after this micro-slice.

Deferred scope:

- No additional ProjectHubView strings were migrated in SP-128. Broader cleanup remains deferred to a later dedicated i18n slice to avoid mixing unrelated UI-copy changes with this closeout.

Assessment: `arc_i18n_project_hub_slice_ready`.

## SP-131 IngestionView Slice

SP-131 migrated the visible `IngestionView.tsx` copy to the Arc i18n catalog.

Migrated keys:

- `ingestion.subtitle`
- `ingestion.disabled`
- `ingestion.progress_title`
- `ingestion.progress_note`
- `ingestion.status_title`
- `ingestion.status_default`
- `ingestion.step`
- `ingestion.pending`
- `ingestion.no_steps`
- `ingestion.completed_review`
- `ingestion.progress`
- `ingestion.run`
- `ingestion.no_run_id`
- `ingestion.safe_workspace`

Intentional non-translation:

- run status machine values stay raw in data/state, including `completed_with_editorial_review` when returned by the backend
- step status values stay raw machine values
- run IDs and job IDs stay raw identifiers

Deferred work:

- realtime ingestion progress hydration
- traffic-light semantic progress colors
- remaining hotspots in `GraphInspector`, `GraphToolbar`, `CanonVaerlView`, `EditorView`, `ReviewQueueView`, and `AIStudioView`

Assessment: `arc_i18n_ingestion_slice_ready`.

## SP-132 AIStudioView Slice

SP-132 migrated the visible `AIStudioView.tsx` placeholder/static copy to the Arc i18n catalog.

Migrated keys:

- `aiStudio.title`
- `aiStudio.subtitle`
- `aiStudio.actions.openHistory`
- `aiStudio.actions.checkCoverage`
- `aiStudio.actions.send`
- `aiStudio.placeholder.title`
- `aiStudio.empty.title`
- `aiStudio.empty.body`
- `aiStudio.input.placeholder`
- `aiStudio.status.placeholder`
- `aiStudio.grounding.title`
- `aiStudio.grounding.value`
- `aiStudio.grounding.note`
- `aiStudio.future.brainstorming`
- `aiStudio.future.brainstormingNote`
- `aiStudio.future.characterLab`
- `aiStudio.future.characterLabNote`

Intentional non-translation:

- Screen remains placeholder-level and early-development.
- No real AI Studio feature behavior was implemented.
- Machine/internal strings stay raw, including route/view IDs, component IDs, and placeholder runtime values.

Remaining hotspots:

- `GraphInspector.tsx`

## SP-133 GraphToolbar Key Migration

SP-133 completed GraphToolbar i18n migration as a key-only cleanup with no class, palette, layout, or graph-behavior changes.

Scope completed:

- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx` now uses toolbar-specific Arc i18n keys for visible filter labels, search placeholder, and reset button text.
- `textifai/web_viewer/react_shell/src/i18n/ui.ts` now includes matching `en`/`es` keys under `graph.toolbar.*`.
- `tests/test_textifai_i18n_ui_strings.py` now asserts GraphToolbar key parity and guards against fallback to old generic key usage in this component.

Still deferred:

- `GraphInspector.tsx` remains separate because its labels and entity-facing copy are broader and more canon-sensitive.
- `CanonVaerlView.tsx` and `EntityFicheView.tsx`
- `ReviewQueueView.tsx`
- deeper `ProjectHubView.tsx` strings, if any remain after earlier slices

Deferred work:

- broader AI Studio behavior, backend calls, persistence, and workflow changes remain out of scope for this slice

Assessment: `arc_i18n_ai_studio_placeholder_slice_ready`.

## SP-134 GraphInspector Chrome Slice

SP-134 migrated `GraphInspector.tsx` static chrome labels to GraphInspector-specific Arc i18n keys without changing graph behavior, layout, styles, class names, or data shape.

Scope completed:

- GraphInspector static chrome labels now route through `graph.inspector.*` keys.
- Empty/helper copy generated by the GraphInspector UI now routes through `graph.inspector.*` keys where it is static chrome.
- Matching English and Spanish catalog entries were added.
- i18n guardrails now assert GraphInspector key parity and prevent fallback to older generic graph keys for migrated labels.

Intentional non-translation:

- Hydrated entity, canon, and payload values remain raw.
- Machine values, paths, entity labels, evidence excerpts, backlinks, outgoing links, authored markdown, and wikilinks remain raw.
- `kind`, status, IDs, note paths, relation targets, canonical labels, aliases, and markdown bodies remain payload/user/canon content, not UI chrome.
- Technical schema key display such as `technical_markdown` remains raw.

Deferred work:

- Ambiguous or dynamic display mappings in GraphInspector remain deferred.
- Canon/VaERL surfaces remain a separate hotspot.
- Editor/entity fiche deeper strings remain separate because they live outside the GraphInspector chrome slice.
- Review Queue remains a separate hotspot.

Assessment: `arc_i18n_graph_inspector_chrome_slice_ready`.

## SP-135 Review Queue Chrome Slice

SP-135 migrated Review Queue static chrome to Arc i18n catalog.

Migrated keys:

- `review.title`
- `review.author_decisions_subtitle`
- `review.apply_decisions`
- `review.rerun_validation`
- `review.search_placeholder`
- `review.severity`
- `review.severity.all`
- `review.severity.high`
- `review.severity.medium`
- `review.severity.low`
- `review.no_linked_chapters`
- `review.accept_relationship`
- `review.accept_alias`
- `review.accept_suggestion`
- `review.create_entity`
- `review.evidence`
- `review.evidence_item`
- `review.chapter`
- `review.technical_details`
- `review.pointer`
- `review.no_structured_evidence`
- `review.decision_type`
- `review.recommendation`
- `review.severity_label`
- `review.editorial_decision`
- `review.needs_author_decision`
- `review.no_structured_reference`
- `review.pronoun_pov`
- `review.unconfirmed_local_candidates`

Classification:

- Static chrome labels migrated: top bar title/subtitle, action buttons, search placeholder, modal section headings, summary note, summary chip labels, evidence modal chrome.
- UI-owned display mappings migrated: severity filter labels (`all/high/medium/low`), fallback no-source label, UI decision CTA variants keyed off `item.actionKind` and `item.hasTarget`.
- Hydrated payload values left raw: `item.title`, `item.human_reason`, `item.summary`, `item.evidence_summary`, `item.action`, `item.source`, `item.raw.review_type`, `item.raw.recommendation`, `ref.reason`, `ref.chapter_label`, `ref.chapter_id`, `ref.pointer_short`, `ref.pointer`, evidence excerpts, summary counts, and severity token text itself.
- Machine/internal values left raw: `choice` IDs, `reviewSeverity` state values (`all|high|medium|low`), `item.actionKind`, `item.materiality`, `item.hasTarget`, summary object keys, payload field names, and CSS/class names.
- Ambiguous/deferred: any future backend-owned localized status/recommendation/severity payloads, entity/canon/evidence content semantics beyond current UI chrome shell.

Intentional non-translation:

- Review Queue static chrome migrated.
- Review modal/filter/action/summary chrome migrated.
- Severity/status labels migrated only where they are UI-owned display mappings.
- Hydrated review payload/entity/evidence/canon values intentionally remain raw.
- Machine review states/action IDs intentionally remain raw.
- Ambiguous dynamic mappings remain deferred.

Assessment: `arc_i18n_review_queue_chrome_slice_ready`.

## SP-136 Canon/VaERL Chrome Slice

SP-136 migrated the safe `CanonVaerlView.tsx` static chrome slice to Arc i18n keys.

Migrated keys:

- `canon.title`
- `canon.subtitle`
- `canon.actions.export_selection`
- `canon.actions.open_evidence`
- `canon.sections.story_bible`
- `canon.empty.select_project`

Classification:

- Static chrome migrated: page title/subtitle, top-bar action buttons, Story Bible section heading, and no-project empty-state copy.
- Existing payload/rendered content left raw: `canonTable`, `legacyNotes`, selected project state, embedded notes, canon payloads, generated/authored content, paths, IDs, and VaERL technical fields.
- Machine/internal values left raw: route/view IDs, component props, CSS/class names, schema keys, API payload fields, and project identifiers.

Deferred work:

- `StoryAliasView.tsx` remains untouched for a later safepoint.
- `EntityFicheView.tsx` and deeper canon/editor surfaces remain untouched because their strings are broader and more payload-sensitive.

Assessment: `arc_i18n_canon_vaerl_chrome_slice_ready`.

## SP-137 StoryAliasView Closeout
- `textifai/web_viewer/react_shell/src/modules/canon/StoryAliasView.tsx` static chrome migrated to i18n.
- `textifai/web_viewer/react_shell/src/App.tsx` legacy embed title callsite migrated only because it belongs to StoryAlias chrome, via `story_alias.legacy_notes_title`.
- Hydrated alias/canon/entity/payload values are intentionally not translated.
- Alias payload values, entity labels, canonical labels, authored/generated content, paths, IDs, and technical fields remain raw.
- Remaining hotspots are deferred; SP-137 does not broaden `App.tsx` migration beyond StoryAlias legacy/embed chrome.

## SP-138 EntityFicheView Chrome Slice
- `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx` static chrome migrated to i18n.
- Migrated chrome: title, save button label, saving label, helper note, unsaved label, and empty placeholder.
- Authored markdown and rendered content are intentionally not translated.
- Wikilinks are intentionally left raw.
- Save/writeback payload messages and backend status text are intentionally left raw.
- Internal IDs, note paths, and entity/canon payload values are intentionally left raw.
- `textifai/web_viewer/react_shell/src/App.tsx` editor chrome is deferred to a later dedicated slice.
- Remaining hotspots: `App.tsx` editor chrome, deeper editor controls if any, and language selector/settings UI.

Assessment: `arc_i18n_entity_fiche_chrome_slice_ready`.

## SP-139 App Editor Chrome Slice
- `textifai/web_viewer/react_shell/src/App.tsx` editor chrome migrated to `t(...)` for scoped editor-shell labels only.
- No broad `App.tsx` sweep happened in SP-139.
- Authored markdown and rendered content remain raw.
- Wikilinks remain raw.
- Project, chapter, and file-path values remain raw.
- Save/write-back/backend payload/status text remains raw unless already part of static editor chrome.
- Ambiguous editor strings were deferred.
- Remaining hotspots: non-editor `App.tsx` chrome and language selector/settings.

Assessment: `arc_i18n_app_editor_chrome_slice_ready`.
