# SP-143 upload staging contract

Safepoint: SP-143

Goal: smallest backend slice for browser upload staging, while preserving future global job state plus per-stage state.

## Endpoints

### `POST /api/ingestion/uploads`
Accept one or more files via `multipart/form-data`.

Success response:

```json
{
  "upload_session_id": "upl_...",
  "files": [
    {
      "file_id": "file_001",
      "filename": "sample_3ch.md",
      "size_bytes": 123,
      "content_type": "text/markdown",
      "status": "staged"
    }
  ]
}
```

### `GET /api/ingestion/uploads?upload_session_id=...`
Return staged upload session metadata only. Do not return raw manuscript content.

## Safe staging root
All accepted files must stay under:
- `runs/web_ingestion_uploads/<upload_session_id>/`

## Accepted now
- `.md`
- `.txt`

## Rejected now
Reject with structured, user-readable error metadata:
- `.pdf`
- `.doc`
- `.docx`
- `.rtf`
- images
- archives
- unknown extensions
- hidden/system filenames
- path traversal names
- empty files
- oversized files

Example rejection shape:

```json
{
  "error": "upload_validation_failed",
  "message": "unsupported extension: .pdf; accepted: .md, .txt",
  "allowed_extensions": [".md", ".txt"],
  "filename": "novel.pdf",
  "extension": ".pdf"
}
```

## Stage-state foundation
SP-143 does not implement full stage progress, but backend contract must preserve both:
- global ingestion/job state
- per-stage/per-subphase state

Canonical foundation doc:
- `docs/operations/ingestion-job-status-contract.md`

Example future-compatible stage snapshot:

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

## Explicitly deferred
- start ingestion from upload
- realtime progress
- retry / continue / skip actions
- frontend upload UI
- 20-chapter validation
- PDF / OCR extraction
- DOC / DOCX conversion

## Roadmap note
- SP-14x: add `.docx` extraction/conversion
- later: add `.pdf` only after quality/error semantics exist
- `.doc` only if strong user demand appears
