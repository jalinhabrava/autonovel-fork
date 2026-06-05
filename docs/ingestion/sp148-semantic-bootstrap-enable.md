# SP-148 — upload-backed 3ch semantic bootstrap enablement

## Summary

Upload-backed 3-chapter ingestion now records explicit semantic-provider availability and distinguishes two execution paths:

- provider-backed semantic bootstrap when provider config is available
- deterministic structural fallback when provider config is unavailable or semantic bootstrap does not complete

## Deterministic fallback

Fallback still creates:

- chapter manifest
- chapter markdown
- minimal author graph
- empty valid review queue
- minimal VaERL shell
- `textifai.project.json` registration

Fallback also records:

- `semantic_provider_unavailable`
- `deterministic_fallback_used`

## Provider-backed semantic path

When bootstrap provider config is available, upload-backed ingestion attempts structured semantic bootstrap and then materializes project-facing artifacts:

- `vaerl/vaerl.json`
- `vaerl/entities.json`
- `vaerl/relationships.json`
- `vaerl/review_queue.json`
- `graph/graph.json`
- `graph/author_graph.json`
- `99_System/markdown_graph_index.json`
- `99_System/markdown_manifest.json`
- `99_System/writer_outcome.json`
- `textifai.project.json`

Progress log records:

- `semantic_provider_available`
- `semantic_bootstrap_started`
- `semantic_bootstrap_completed`

## Provider config

Semantic bootstrap uses existing provider abstraction through `providers.text_provider.get_text_provider(...)`.

Typical bootstrap config:

- `AUTONOVEL_BOOTSTRAP_PROVIDER`
- `AUTONOVEL_BOOTSTRAP_MODEL`
- provider key for selected provider, for example `OPENAI_API_KEY`

No live provider is required for tests.

Current state:

- provider setup is env/config driven
- no user-facing Settings/Profile provider screen exists yet
- future Settings/Profile should show configured/unconfigured state, provider name, selected model, last provider error, semantic/fallback state, and a pre-ingestion warning when provider config is missing or invalid

## Future settings note

There is no user-facing provider/settings screen yet. Provider selection stays env/config-driven for now.

When Settings/Profile exists, it should surface:

- selected provider and model
- provider availability status
- warnings for missing or unsafe model config
- status of semantic bootstrap capability

## Stage status semantics

Viewer job detection now distinguishes:

- `semantic_ready`
- `structural_only`
- `pending`

Structural-only projects remain openable, but semantic phases should warn instead of implying semantic completion.

## Failure and fallback behavior

- provider missing: structural fallback remains available and warning is recorded
- semantic bootstrap failure: structural fallback may still produce openable project if chapter materialization succeeds
- no fake semantic completion is reported without semantic artifacts

## Deferred

Still deferred:

- 20-chapter validation
- cancellation around long semantic jobs
- provider cost controls
- richer review-quality policies
- PDF/DOC/DOCX semantic ingestion support

## Live DeepSeek 3ch validation

- Date/time: 2026-06-05 07:53:46 UTC to 07:58:47 UTC
- Provider: DeepSeek
- Model: `deepseek-chat`
- Fixture used: `/tmp/sp148_live_deepseek_3ch.md`
- API path: upload via `POST /api/ingestion/uploads`, start via `POST /api/ingestion/jobs`, inspect via `GET /api/ingestion/jobs/<job_id>`
- Job id: `ing_20260605T075346_3f01feb0`
- Output root: `/home/david/projects/autonovel-fork/runs/web_ingestion/20260605T075346Z_sp148_live_deepseek_rich_3ch_chat`
- Project id: `home__david__projects__autonovel-fork__runs__web_ingestion__20260605T075346Z_sp148_live_deepseek_rich_3ch_chat`
- Provider events observed:
  - `semantic_provider_available`
  - `pipeline_started`
  - `global_normalization_batch_started`
  - `global_normalization_batch_completed`
  - `chapter_extraction_started`
  - `chapter_extraction_completed`
  - `semantic_bootstrap_started`
  - `semantic_bootstrap_completed`
  - `structured_bootstrap_imported`
- Result: `semantic_ready`
- Artifact counts:
  - `vaerl/entities.json`: 19 entities
  - `vaerl/relationships.json`: 109 relationships
  - `vaerl/review_queue.json`: 13 items
  - `graph/graph.json`: 21 nodes / 435 edges
  - `graph/author_graph.json`: 21 nodes / 127 edges
- Warnings/errors:
  - Global normalization initially hit strict language-validation warnings and recovered by subdivision
  - Chapter extraction for `ch_002` and `ch_003` recorded parse failures after retries, but pipeline still completed and materialized semantic artifacts
- Graph/Editor/Review artifacts are expected to load from semantic package
- 20ch validation remains deferred

### Live validation notes

- Attempt with `AUTONOVEL_BOOTSTRAP_MODEL=auto` failed against DeepSeek with HTTP 400 because repo model planning treated `auto` as a literal provider model.
- Explicit `AUTONOVEL_BOOTSTRAP_MODEL=deepseek-chat` succeeded for live semantic validation.
- For SP-148 closeout, `auto` remains documented as unsafe/unsupported for DeepSeek bootstrap unless separately fixed.
