# `.textifai` Live Project Folder Contract

## Goal
Define live editable project layout for local-first TextifAI.

## Required structure
- `textifai.project.json`
- `db/textifai.sqlite`
- `markdown/Chapters/`
- `markdown/Canon/`
- `evidence/`
- `vectors/`
- `reports/`
- `runs/`
- `exports/`

## Ownership contract
- Markdown (`markdown/*`): author-facing source content.
- SQLite (`db/textifai.sqlite`): operational state and indexes.
- JSON (`reports/*`, snapshot exports): diagnostics, snapshots, transfer aids.

## Live operation rules
- Live editing targets Markdown + SQLite.
- JSON artifacts are generated snapshots; never authoritative live CRUD source.
- `textifai.project.json` remains entrypoint manifest for discovery/open.
