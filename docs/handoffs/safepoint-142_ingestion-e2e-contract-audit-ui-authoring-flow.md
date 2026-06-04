# SP-142 — ingestion E2E contract audit for UI-driven authoring flow

## Preflight

- Branch: `phase-1.4-authoring-workbench-projectstore`
- Worktree: clean at audit start
- Recent head: `e5bd026 sp-141 add arc favicon`
- Scope: audit/contract design only; no upload/progress implementation

## Executive finding

Arc does not yet have the target upload → ingest → realtime progress → ready project UI flow.

Current Arc ingestion surface is a read-only status shell over existing project `run_status` and historical local-path ingestion jobs. Backend has a controlled local-path job API that can execute `scripts/textifai.py init`, but it does not expose browser file upload staging, upload listing, uploaded-file-backed job creation, stage-level realtime progress, or automatic project-list/selection transition on completion.

## Current-state classification

| Area | Classification | Evidence |
| --- | --- | --- |
| Upload support | H — missing for Arc browser UI | `build_ingestion_config()` returns `can_upload: False` and `future_input_modes: ["upload"]` in `textifai/web_viewer/server.py:21`; no `/api/ingestion/uploads` route exists. |
| Ingestion pipeline | B — CLI/script exists | Job command builds `uv run python scripts/textifai.py init --vault-root ... --source-root ... --project-title ...` in `textifai/web_viewer/ingestion_jobs.py:478`. |
| Ingestion HTTP API | Partial C — local-path job API only | `GET/POST /api/ingestion/jobs` and job detail/log GET exist in `textifai/web_viewer/server.py:127`. |
| ProjectStore creation/update | D — exists for project roots and editor saves | `open_project(project.root)` supports chapter/entity saves in `textifai/web_viewer/server.py:189`; store imports chapter manifest in `textifai/project_store/store.py`. |
| Job/progress status | Partial E — job status exists, stage progress absent | `IngestionJob.snapshot()` exposes `status`, logs, artifacts, result flags in `textifai/web_viewer/ingestion_jobs.py:193`; no per-stage progress updates from running backend. |
| Frontend ingestion UI | F — placeholder/display-only | `IngestionView` only renders `runStatus.steps` and `ingestionJobs`, with disabled action, in `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx:15`. |
| Graph/Editor/Review refresh after ingestion | Partial G — project views work after selection; no completion handoff | App loads selected project context through `fetchProjectDetail`, `fetchGraph`, `fetchReviewQueue`, `fetchArtifacts` in `textifai/web_viewer/react_shell/src/App.tsx:557`; no polling/reselect after job completion. |
| Missing entirely | Upload staging, upload metadata contract, uploaded-files card/list, start-ingestion UI mutation, real stage-progress contract, terminal ready transition, 3-chapter E2E fixture path from UI. |

## Frontend ingestion audit

### Visible UI

- `IngestionView` renders top bar, disabled secondary action, progress card grid, status metric, run id, safe-workspace flag, and historical job rows.
- It consumes `runStatus: ProjectDetail['run_status']` and `ingestionJobs: IngestionJob[]` only.
- `runStatus.steps` controls progress-card label, status, and percent width. Values are clamped to 0–100 before rendering.
- Empty progress state shows `ingestion.no_steps`.

### Static/placeholders

- Top-bar action is disabled; no click handler.
- `ingestionConfig` is fetched in `App.tsx` but not used by `IngestionView`.
- `ProjectHubView` has “New ingestion” / “Open manifest” style affordances without mutation wiring.
- i18n copy still frames this as future/local-first project shell, not browser-upload E2E.

### Missing for target flow

- File input/dropzone and validation.
- Uploaded files card/list.
- POST client for uploads.
- POST client for starting a job from uploaded files.
- Active job polling or event stream.
- Error, cancel, retry, and log detail UX.
- Completion handler that refreshes `/api/projects`, selects new ready project, and navigates to Graph/Editor/Review affordances.

## Backend/API audit

### Existing endpoints

- `GET /api/ingestion/config`: returns local-path config; upload disabled.
- `GET /api/ingestion/jobs`: returns historical jobs plus summary.
- `GET /api/ingestion/jobs/{job_id}`: returns job snapshot.
- `GET /api/ingestion/jobs/{job_id}/log`: returns redacted log tail.
- `POST /api/ingestion/jobs`: creates a controlled local-path ingestion job.
- `GET /api/projects`: lists catalog projects.
- `GET /api/projects/{project_id}`: reads project detail.
- `GET /api/projects/{project_id}/graph`: returns graph payload.
- `GET /api/projects/{project_id}/canon`: returns canon payload.
- `GET /api/projects/{project_id}/artifacts`: returns artifacts list.
- `GET /api/projects/{project_id}/note`: reads markdown note.
- `GET /api/projects/{project_id}/entity-card`: reads entity card view model.
- `POST /api/projects/{project_id}/chapters/{chapter_id}/save`: saves ProjectStore-backed chapter markdown.
- `POST /api/projects/{project_id}/entities/{entity_id}/save`: saves ProjectStore-backed entity fiche markdown.
- `POST /api/projects/{project_id}/chapters/{chapter_id}/reanalyze`: placeholder 202 `not_implemented` response.

### Ingestion execution path

- Current job contract requires `source_root`, `project_title`, and `run_name`.
- `source_root` must already exist as local directory; browser upload does not feed this path.
- Job output target is forced under `runs/web_ingestion/<timestamp>_<slug>`.
- Execution uses subprocess args list; no shell interpolation.
- Result detection checks `99_System/obsidian_import.json`, `99_System/review_queue.json`, `semantic_invariants_audit.json`, and `run_comparability_manifest.json`.
- If output has `99_System` and inspectable artifacts, job exposes `project_id` computed from output path.

### Pipeline output path

- Preferred active rail is `scripts/textifai.py init` → `textifai.obsidian.cli` → `prepare_obsidian_project` → structured bootstrap.
- Structured bootstrap writes `obsidian_import.json`, `review_queue.json`, semantic audits, comparability manifest, materialized chapters/notes, graph artifacts, and `reports/run_status.json`.
- `ProjectReader` surfaces `run_status` from `reports/run_status.json`.
- Graph/Editor/Review can become usable after catalog sees output project and app selects/loads it.

## Proposed minimum backend contract

### Upload staging

`POST /api/ingestion/uploads`

- Accepts one or more manuscript/document files as multipart form-data.
- Stores files under a safe non-production staging root, for example `runs/web_ingestion_uploads/<session_or_draft_id>/`.
- Rejects path traversal, empty files, hidden/system paths, unsupported extensions, and size over configured limit.
- Returns:

```json
{
  "upload_session_id": "upl_20260604T120000_abcd1234",
  "files": [
    {
      "file_id": "file_001",
      "filename": "sample_3ch.md",
      "size_bytes": 12345,
      "content_type": "text/markdown",
      "status": "staged"
    }
  ]
}
```

`GET /api/ingestion/uploads?upload_session_id=...`

- Returns current staged files and validation state.
- No raw manuscript content in response.

### Job lifecycle

`POST /api/ingestion/jobs`

- Extend existing route to accept `upload_session_id` OR keep local-path job under a separate explicit mode.
- For upload mode, backend converts staged upload session into controlled `source_root` and calls existing `scripts/textifai.py init` path.
- Returns `202` and job snapshot.

`GET /api/ingestion/jobs/{job_id}`

- Keep existing snapshot fields.
- Add real backend-derived `stage_status` and `project_ready` fields:

```json
{
  "job_id": "ing_20260604T120001_abcd1234",
  "status": "running",
  "project_id": null,
  "project_ready": false,
  "stage_status": {
    "schema": "textifai.ingestion_job_progress.v1",
    "steps": [
      { "id": "upload_staged", "label": "Files staged", "status": "completed", "progress": 100 },
      { "id": "source_inventory", "label": "Source inventory", "status": "running", "progress": 40 },
      { "id": "chapter_detection", "label": "Chapter detection", "status": "pending", "progress": 0 },
      { "id": "semantic_ingestion", "label": "Semantic ingestion", "status": "pending", "progress": 0 },
      { "id": "project_materialization", "label": "Project materialization", "status": "pending", "progress": 0 },
      { "id": "ready", "label": "Workspace ready", "status": "pending", "progress": 0 }
    ]
  }
}
```

`GET /api/ingestion/jobs/{job_id}/events` or polling-only MVP

- Optional SSE later.
- Polling MVP acceptable if progress values come from backend/job metadata, not timers.

### Ready handoff

On terminal success:

- `status: "succeeded"`
- `project_ready: true`
- `project_id` populated
- `result_detected: true`
- `review_queue_available` and `inspectable_artifacts_available` populated
- Frontend refreshes `/api/projects`, selects `project_id`, loads project detail/graph/review/artifacts, and enables Graph/Editor/Review navigation.

## Proposed 3-chapter E2E contract test

### Fixture

- Add a tiny manuscript source fixture with exactly 3 chapters.
- Use plain Markdown or text in a staged-upload-like directory.
- Keep content cheap and deterministic; do not run 20-chapter fixture in SP-142.

### Backend contract test

- Exercise upload staging API with the 3-chapter fixture.
- Start ingestion job from `upload_session_id`.
- Poll job until terminal using short timeout in integration mode only.
- Assert:
  - job reaches `succeeded`
  - `project_ready` is true
  - `project_id` is present
  - output root stays under safe root
  - `99_System/obsidian_import.json` exists
  - `99_System/review_queue.json` exists
  - `reports/run_status.json` exists
  - project catalog can open it
  - `/api/projects/{project_id}/graph` returns nodes/edges payload
  - `/api/projects/{project_id}` includes editor chapters
  - review queue endpoint returns list/summary shape

### Frontend contract test

- Mock backend responses, not progress timers.
- Assert upload list renders from API metadata.
- Assert start button POSTs job request.
- Assert polling updates visible stage progress from backend payload.
- Assert terminal success refreshes projects and offers Graph/Editor/Review actions.

## Risks and sequencing

1. Upload parser choice: current server uses `BaseHTTPRequestHandler`, so multipart parsing needs careful standard-library handling or deliberate server-stack upgrade. Keep this isolated.
2. Progress source: current pipeline writes final `run_status`, but not live stage progress. Need backend job metadata updates around known subprocess milestones or structured pipeline callbacks.
3. Catalog refresh: `ProjectCatalog` may need refresh/re-scan after new output appears; frontend also must refresh after job success.
4. ProjectStore readiness: generated output must include enough `.textifai`/manifest/chapter metadata for Editor save support if acceptance includes ProjectStore-backed editing.
5. No fake progress: frontend must never infer stage percentages from elapsed time.

## Recommended next safepoints

### SP-143 — backend upload staging contract

- Add safe upload staging endpoints and tests.
- Do not start ingestion from UI yet.
- Acceptance: upload → uploaded-files metadata list.

### SP-144 — backend uploaded-job start + real job status

- Extend job creation to accept `upload_session_id`.
- Add backend-derived stage status to job snapshot.
- Acceptance: 3-chapter staged upload starts real ingestion and produces inspectable project.

### SP-145 — Arc ingestion UI wiring

- Wire upload card/list, start action, polling, error states, and completion handoff.
- Acceptance: UI-driven 3-chapter upload → ingest → ready → Graph/Editor/Review usable.

### SP-146 — 20-chapter validation pass

- Run real 20-chapter ingestion after 3-chapter path is stable.
- Acceptance: final UI state matches useful pre-ingested project state.
