# Safepoint 116 — Chapter title write-back sync

## Scope
- Guarded chapter markdown + title write-back through ProjectStore.
- Bidirectional title sync between editor H1 and chapter rail.
- Manifest snapshot sync as export/compat fallback.

## Runtime verification
- live_save_endpoint_verified=true
- save_success_json=true
- conflict_json_409=true
- backup_created=true
- dirty_state_needs_reanalysis=true
- real_project_safe=true
- manifest_snapshot_updated=true
- markdown_h1_updated=true

## Runtime proof (safe copy)
- Project source: `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai`
- Verification target copy: `/tmp/TextifAIProjectsTitleRuntime/OnT_Spanish_20ch.textifai`
- Viewer: `127.0.0.1:8872`
- Root `/` HTTP 200: true
- `/api/projects/<id>` OK: true
- `editor_chapters.source_used=project_store`
- Save success: true
- Manifest updated: true
- Markdown H1 updated: true
- Conflict test stale expected hash returns HTTP 409 JSON hash_mismatch: true
- Manuscript unchanged on real project: true

## Notes
- No provider calls.
- No semantic write-back regeneration.
- Title lives in SQLite + Markdown + manifest snapshot.
- Export/import `.txtfai` should preserve titles through live store + snapshot layers.
