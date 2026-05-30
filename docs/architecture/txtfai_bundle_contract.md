# `.txtfai` Bundle Contract

## Definition
`.txtfai` is zip-like portable bundle format for TextifAI projects.

## Non-goal
`.txtfai` is not primary live editing store.

## Import/export flow
1. Open `.txtfai` bundle.
2. Validate bundle manifest/version.
3. Extract/import into `.textifai` live folder.
4. Work live against Markdown + SQLite.
5. Export back to `.txtfai` for transfer/backup.

## Include/exclude policy
- Include by default: manifest, Markdown, SQLite, evidence, reports.
- Vector cache (`vectors/`) policy: optional include; safe to exclude if rebuildable.

## Validation manifest
Bundle must include manifest with:
- schema/version;
- project identity;
- checksums for included payloads;
- migration compatibility info.

## Version and migration
- Bundle schema versioned independently from SQLite schema.
- Import path runs migration checks before opening as live project.

## Backup/restore
- `.txtfai` serves archival backup/restore boundary.
- Restore always materializes `.textifai` live folder before edits.
