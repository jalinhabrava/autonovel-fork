# SP-122B Entity Fiche Markdown Writeback

## Scope
- Entity fiche Markdown save path enabled when `expected_hash` matches current disk hash.
- No semantic mutation beyond dirty marking.
- No VaERL, Graph, or Review regeneration.

## Backend / API
- `ProjectStore.save_entity_fiche_markdown(...)` saves fiche Markdown and returns `backup_path`, `new_hash`, `semantic_state=needs_reanalysis`, and `dirty_state=true`.
- HTTP save endpoint returns JSON on success and `409` JSON on hash conflict.
- Path escape blocked before write.

## UI Save Behavior
- Fiche editor shows save button, local dirty notice, and save/conflict messaging.
- Save state is explicit; success says reanalysis pending.
- Conflict keeps local buffer intact.

## Preservation Rules
- Frontmatter preserved byte-for-byte when present.
- Wikilinks preserved exactly, including `[[Sera]]`.
- UTF-8 content preserved.
- Structured data stays outside MDX body.

## Backup / Conflict
- Backup file written before overwrite under `.textifai/history/entities/<entity_id>/`.
- Stale hash returns conflict and does not write.

## Semantic Dirty State
- Save marks entity dirty as `needs_reanalysis` via `dirty_states`.
- No silent semantic mutation.

## Validation
- `tests.test_textifai_entity_fiche_writeback` passes.
- `tests.test_textifai_chapter_writeback` passes.
- `tests.test_textifai_entity_fiche_semantic_contract` passes.
- `tests.test_textifai_graph_fiche_editor_surface` passes.
- `tests.test_textifai_i18n_ui_strings` passes.

## Runtime Proof
- temp_real_project_copy_used=true
- endpoint_save_verified=true
- conflict_409_verified=true
- wikilink_preserved=true
- no_semantic_mutation=true
- no_graph_regeneration=true
- no_review_regeneration=true

Runtime verification used temp copy only:

- Source real project: `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai`
- Temp copy: `/tmp/sp122b_visual_project/OnT_Spanish_20ch.textifai`
- Viewer command: `uv run python -m textifai.web_viewer.server --root /tmp/sp122b_visual_project --host 0.0.0.0 --port 8872`
- `GET /` -> `200`
- `GET /api/projects` -> `200`
- `GET /api/projects/tmp__sp122b_visual_project__OnT_Spanish_20ch.textifai` -> `200`
- `GET /api/projects/tmp__sp122b_visual_project__OnT_Spanish_20ch.textifai/graph` -> `200`

Endpoint proof on temp copy:

- Seeded temp-copy SQLite rows for `sera`, `ren`, and `magia` inside `/tmp/sp122b_visual_project/.../.textifai/db/textifai.sqlite`.
- Valid hash save: `POST /api/projects/tmp__sp122b_visual_project__OnT_Spanish_20ch.textifai/entities/sera/save` -> `200`.
- Success payload returned `backup_path=.textifai/history/entities/sera/20260601T080220Z_2b31eacd9410.md`, `semantic_state=needs_reanalysis`, and `dirty_state=true`.
- Stale hash save returned `409` with `error=hash_mismatch`.
- Saved markdown preserved `[[Sera]]` on disk.
- No VaERL/Graph/Review regeneration command was run.

## Visual Proof
- visual_builder_skill_used=true
- visual_save_ui_seen=true
- screenshot_path=/tmp/sp122b_graph_open.png
- screenshot_path=/tmp/sp122b_graph_select_Ren.png
- screenshot_path=/tmp/sp122b_graph_select_Sera.png
- screenshot_path=/tmp/sp122b_graph_select_Magia.png

Visual proof used `codex-visual-builder-guild` minimum useful pass against the temp real-project copy.

- Graph rendered with node sheet inspector.
- `Ren`, `Sera`, and `Magia` selected via `graph_select` URL flow after opening the temp project.
- Fiche save control/status visible in node fiche panel.
- Save status copy is honest: it reports save unavailable when no loaded hash is available in the selected panel context.
- UI does not claim relationships, Graph, or Review were regenerated.
- SP-121C graph/ficha sheet layout remained intact in screenshots.

## Explicit Non-Goals
- No semantic mutation.
- No VaERL write-back.
- No Graph/Review regeneration.
- No Review merge propagation.
