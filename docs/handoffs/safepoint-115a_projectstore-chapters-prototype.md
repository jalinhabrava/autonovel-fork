# Safepoint 115A — ProjectStore chapters prototype

## Scope
- Prototype `ProjectStore` SQLite chapter bootstrap/read path.
- Wire viewer reader fallback to use ProjectStore chapter list when SQLite exists.
- No chapter write-back.
- No provider calls.

## Runtime verification
- `live_viewer_projectstore_verified=true`
- `route_status_code=200`
- `detail_route_body_present=true`
- `viewer_source_used=project_store`
- `editor_chapter_count=20`
- `db_exists=true`
- `schema_version=0`

## Route debug outcome
- Detail route `/api/projects/<id>` is valid.
- Verification harness parsing issue found: response splitting expected CRLF (`\r\n\r\n`) while server response used LF (`\n\n`).
- Result: body appeared empty in harness, but server returned JSON correctly.

## Changed files (SP-115A)
- `textifai/project_store/schema.sql`
- `textifai/project_store/__init__.py`
- `textifai/project_store/store.py`
- `textifai/web_viewer/project_reader.py`
- `tests/test_textifai_project_store_sqlite.py`

## Notes
- SQLite DB location: `<project>/.textifai/db/textifai.sqlite`.
- Generated DB remains outside repo and untracked.
