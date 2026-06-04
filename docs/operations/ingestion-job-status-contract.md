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

## Stage snapshot shape
Example only; backend may add fields later as long as semantics stay stable.

```json
{
  "id": "chapter_detection",
  "status": "warning",
  "progress": 100,
  "summary": "3 chapters detected",
  "warnings": [],
  "errors": [],
  "actions": ["inspect", "continue_with_warnings"]
}
```

## Upload staging contract for SP-143
- Browser upload staging stores files under `runs/web_ingestion_uploads/<upload_session_id>/`.
- Upload API returns metadata only.
- Upload API does not start ingestion.
- Upload API does not fake progress.
- Upload API does not accept path traversal, empty files, hidden/system filenames, oversized files, or unsupported extensions.

## Explicitly deferred
- start ingestion from upload
- realtime progress updates
- retry / continue / skip actions
- frontend upload UI
- 20-chapter validation target
- PDF / OCR / DOC / DOCX conversion

## Notes
- SP-143 only establishes upload staging plus state-shape foundation.
- Later phases can map stage snapshots into job history, UI progress, and action controls.
