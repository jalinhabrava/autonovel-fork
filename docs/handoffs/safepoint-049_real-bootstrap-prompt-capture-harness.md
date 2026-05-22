# Real Bootstrap Prompt Capture Harness

## Product Reading

El objetivo ya no es fabricar un prompt packet artificial. El objetivo es capturar requests reales que genera el pipeline activo de TextifAI después de leer fuente, detectar capítulos y planificar extracción, justo antes de provider. La captura debe ser provider-free y servir para que el usuario suba el prompt real a ChatGPT sin commitear texto privado.

## Scope

- Añadir script dev para ejecutar `run_structured_bootstrap_v1(...)` con provider fake/capturing.
- Guardar requests capturadas como JSON y Markdown copiables.
- Añadir tests con fuente sintética pequeña.
- No tocar runtime productivo, provider code, chunking, viewer ni schemas.

## Files Changed

- `scripts/dev/capture_bootstrap_prompts.py`
- `tests/test_textifai_real_bootstrap_prompt_capture_harness.py`
- `docs/handoffs/safepoint-049_real-bootstrap-prompt-capture-harness.md`

## What Was Inspected

- `textifai/import_review/structured_bootstrap_v1.py`
- `textifai/import_review/chapterizer.py`
- `textifai/bootstrap/source_reader.py`
- `providers/text_provider.py`
- `tests/test_textifai_structured_bootstrap_v1.py`
- Existing trace paths:
  - `99_System/api_call_traces`
  - `99_System/llm_call_ledger.jsonl`
  - `request_trace_sample_chapters`

## Existing Trace Capability

Existing `api_call_traces` writes request JSON for:
- first global normalization batch;
- sampled chapter extraction requests;
- chapter reduction request for large chapters.

Existing ledger stores hashes/token estimates/status, not full prompt payload. Existing trace is useful but not enough as standalone controlled capture because it writes under vault output, lacks Markdown copy artifacts, and does not capture every provider request uniformly.

## Capture Strategy

`scripts/dev/capture_bootstrap_prompts.py` patches `get_text_provider` inside script execution to a local fake provider. The real bootstrap pipeline still builds inventory, detects chapters, builds global/chapter prompts and calls `provider.generate(...)`; the fake provider intercepts `TextGenerationRequest`, writes capture artifacts, and returns minimal valid JSON so pipeline can continue.

## Provider-free Guarantee

- No provider/API client used.
- `get_text_provider_config_error` patched to allow fake provider.
- `get_text_provider` patched to fake capture provider.
- No secrets needed.
- No network needed by harness.

## How To Capture Real Prompts

Run from repo root:

```bash
uv run python scripts/dev/capture_bootstrap_prompts.py \
  --source-root /path/to/source \
  --output-root /tmp/textifai_prompt_capture \
  --primary-language ja \
  --max-chapters 3
```

Optional single file:

```bash
uv run python scripts/dev/capture_bootstrap_prompts.py \
  --source-root /path/to/source-root \
  --source-file /path/to/source-root/novel.md \
  --output-root /tmp/textifai_prompt_capture \
  --primary-language ja \
  --max-chapters 3
```

The command prints path to `capture_manifest.json`.

## Output Files

Capture directory format:

```text
/tmp/textifai_prompt_capture/<timestamp>/
  capture_manifest.json
  request_001_bootstrap_global_normalization.json
  request_001_bootstrap_global_normalization.md
  request_002_bootstrap_chapter_extraction_ch_001.json
  request_002_bootstrap_chapter_extraction_ch_001.md
```

For long chapters, additional provider requests may appear for partial extraction/reduction.

## What To Upload To ChatGPT

Upload/copy one `.md` request file from capture output. For first check, use:

- global normalization: `request_001_bootstrap_global_normalization.md`
- chapter extraction: first `request_*_bootstrap_chapter_extraction_ch_*.md`

Do not upload `capture_manifest.json` unless needed for metadata.

## Source Privacy Policy

Captured Markdown/JSON can contain private source text. Do not commit capture output. Default output is `/tmp/textifai_prompt_capture`. Tests use only synthetic source text.

## Tests Added / Updated

- `tests/test_textifai_real_bootstrap_prompt_capture_harness.py`

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `uv run python scripts/textifai.py init --help`
- `uv run python scripts/textifai.py replay-downstream --help`
- `git status --short`
- `git diff --stat`

## Data Written

Versioned:
- dev script;
- tests;
- this handoff.

Generated during tests:
- temporary directories under system temp only.

No `runs/**`. No real `vault/**`.

## Safety Constraints

- No provider calls.
- No red/API/secrets.
- No real source prompt captures committed.
- No write-back.
- No runtime semantic changes.
- No chunking implementation changes.

## Known Limitations

- Fake provider returns stub JSON to let pipeline proceed; captured request input is real, model output is not.
- Existing pipeline trace still writes into temp vault created by script, but final export lives in explicit capture output root.
- Long-chapter chunk/reduction path is capturable if triggered by real source/token budget, but tests only cover small synthetic chapters.

## Future Extensions

- Add optional `--keep-temp-vault` for debugging.
- Add redaction/sampling mode for safer sharing.
- Add dedicated long-chapter synthetic test for partial/reduction request capture.

## Runtime Changes

None. Script is dev harness; runtime product code unchanged.

## Provider Calls

None.

## Write-back

None.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.M-b4 — Real Captured Prompt ChatGPT Trial & Gap Audit, then Phase 1.3.N — Chunking & Token Budget Audit.
