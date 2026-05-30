# Safepoint 116 — Chapter Markdown write-back

## Scope
- Guarded chapter markdown write-back via ProjectStore.
- Viewer endpoint save + conflict JSON.
- Editor save integration with hash guard UX.

## Runtime verification
- live_save_endpoint_verified=true
- save_success_json=true
- conflict_json_409=true
- backup_created=true
- dirty_state_needs_reanalysis=true
- real_project_safe=true

## Runtime proof (safe copy)
- Project source: `/home/david/TextifAIProjects/OnT_Spanish_20ch.textifai`
- Verification target copy: `/tmp/TextifAIProjectsRuntimeThread/OnT_Spanish_20ch.textifai`
- Viewer: `127.0.0.1:8872`
- Root `/` HTTP 200: true
- `/api/projects/<id>` OK: true
- `editor_chapters.source_used=project_store`
- Save success: true
- Hash old/new equal on no-op save: true
- Backup path emitted and file exists: true
- Conflict test stale expected hash returns HTTP 409 JSON hash_mismatch: true
- Manuscript unchanged after no-op save: true
- VaERL/Graph/Review unchanged by save flow: true

## Notes
- No provider calls.
- No semantic write-back regeneration.
- No real project manuscript mutation left behind.
