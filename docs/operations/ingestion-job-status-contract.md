# Ingestion job status contract

Scope: backend contract for TextifAI ingestion lifecycle and stage snapshots.

## Current rule
Do not model ingestion as one global progress bar only. Backend must expose:
- global ingestion/job state
- per-stage / per-subphase state

## Job status enum
Use this future-compatible set for job snapshots and API payloads:
- `queued`
- `running`
- `blocked`
- `completed`
- `completed_with_warnings`
- `failed`
- `cancelled`

## Stage status enum
Use this future-compatible set for stage snapshots:
- `pending`
- `running`
- `completed`
- `warning`
- `blocked`
- `failed`
- `skipped`

## Job request modes
`POST /api/ingestion/jobs` supports exactly one source mode:
- local path job: `source_root`
- upload-backed job: `upload_session_id`

Rules:
- do not accept both source inputs
- do not accept neither
- do not accept arbitrary browser file paths
- upload-backed jobs resolve through staged upload metadata under `runs/web_ingestion_uploads/<upload_session_id>/`
- upload-backed jobs reject unknown sessions and sessions with no valid staged `.md` / `.txt` files

## Job snapshot shape
Backend payloads must keep existing fields and add `stage_status`.

```json
{
  "job_id": "ing_20260604T120001_abcd1234",
  "status": "running",
  "input_mode": "upload_session",
  "upload_session_id": "upl_20260604T120000_abcd1234",
  "stage_status": {
    "schema": "textifai.ingestion_job_progress.v1",
    "global_status": "running",
    "current_stage_id": "ingestion_running",
    "progress": 0,
    "stages": [
      {
        "id": "upload_staged",
        "label": "Upload staged",
        "status": "completed",
        "progress": 100,
        "summary": "Files are staged under controlled upload root",
        "warnings": [],
        "errors": [],
        "retry_count": 0,
        "actions": ["inspect"]
      }
    ]
  }
}
```

## Stage snapshot semantics
Stage snapshots are backend-owned and coarse. They may include:
- `status`
- `summary`
- `warnings`
- `errors`
- `retry_count`
- `actions`

## Supported stage actions now
Keep actions conservative:
- `inspect` when logs/job detail exist

Do not advertise these unless backend truly supports them:
- `retry_stage`
- `retry_failed_items`
- `continue_with_warnings`
- `skip_stage`
- `cancel_job`

## Current backend stage mapping
Backend may expose these coarse stages:
- `upload_staged`
- `job_queued`
- `ingestion_running`
- `artifacts_detected`
- `project_ready`

Current limitation:
- subprocess pipeline does not expose true granular live callbacks yet
- no fake progress timers
- use backend/job metadata only
- if only coarse progress is known, prefer truthful `0` / `100` or omit finer values

## Upload staging contract for SP-143
- Browser upload staging stores files under `runs/web_ingestion_uploads/<upload_session_id>/`.
- Upload API returns metadata only.
- Upload API does not start ingestion.
- Upload API does not fake progress.
- Upload API does not accept path traversal, empty files, hidden/system filenames, oversized files, or unsupported extensions.

## Explicitly deferred
- realtime progress updates
- retry / continue / skip actions
- frontend upload UI
- 20-chapter validation target
- PDF / OCR / DOC / DOCX conversion

## Notes
- SP-143 established upload staging plus state-shape foundation.
- SP-144 connects upload-backed jobs and adds backend-owned job/stage snapshots.
- Later phases can map stage snapshots into job history, UI progress, and action controls.
