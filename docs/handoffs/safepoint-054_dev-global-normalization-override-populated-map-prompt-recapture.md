# Dev Global Normalization Override + Populated Map Prompt Recapture

## Product Reading

- `safepoint-053` proved a manual global normalization sample can produce a non-empty canonical map via real TextifAI builder code.
- Remaining gap was chapter extraction recapture with populated `CANONICAL_ENTITY_MAP`.
- This phase adds a dev-only override path in capture harness to inject manual global normalization and recapture chapter prompts without provider/API calls.
- This phase does not evaluate model response quality yet.

## Scope

- Add `--global-normalization-json` dev-only option to `scripts/dev/capture_bootstrap_prompts.py`.
- Keep legacy behavior unchanged when override is absent.
- Use override only for `bootstrap_global_normalization` fake response.
- Preserve normal pipeline flow so real runtime builder path creates canonical map for chapter prompt construction.
- Add provider-free tests for option behavior, override behavior, canonical map artifact, and prompt content checks.
- Run real recapture into `/tmp` only.

## Files Changed

- `scripts/dev/capture_bootstrap_prompts.py`
- `tests/test_textifai_real_bootstrap_populated_map_capture_harness.py`
- `docs/handoffs/safepoint-054_dev-global-normalization-override-populated-map-prompt-recapture.md`

## Global Normalization Override

- New CLI option: `--global-normalization-json /path/to/global_normalization.json`.
- Override file is loaded as JSON object and validated for top-level keys `work`, `entities`, `merge_plan`.
- If missing/invalid, harness exits with clear `SystemExit` error.
- If option is omitted, harness behavior remains legacy.

## Capture Harness Behavior

- `_CaptureProvider.generate()` still captures every `TextGenerationRequest`.
- For task `bootstrap_global_normalization`, provider returns override payload when configured.
- For other tasks, provider still returns local stub payloads.
- Harness still patches provider resolver and never calls real provider APIs.

## Canonical Map From Override

- Harness now writes `canonical_entity_map_from_override.json` into capture output directory when override enabled.
- This file is generated with real `build_canonical_entity_map(...)` imported from runtime module.
- Manifest now includes:
  - `global_normalization_override_enabled`
  - `global_normalization_override_json`
  - `canonical_entity_map_pipeline_path`
  - `canonical_entity_map_from_override`

## Real Prompt Recapture

- Command executed:

```bash
uv run python scripts/dev/capture_bootstrap_prompts.py \
  --source-root "/home/david/OnT" \
  --source-file "/home/david/OnT/王者の杖.md" \
  --output-root "/tmp/textifai_prompt_capture_jp_populated_map_after_sp053" \
  --primary-language ja \
  --max-chapters 3 \
  --global-normalization-json "tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_global_normalization_ja_batch_001_after_sp051.json"
```

- Latest capture directory:
  - `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260522T163323Z`
- Captured files include:
  - `request_001_bootstrap_global_normalization.{json,md}`
  - `request_002_bootstrap_chapter_extraction_ch_001.{json,md}`
  - `request_003_bootstrap_chapter_extraction_ch_002.{json,md}`
  - `request_004_bootstrap_chapter_extraction_ch_003.{json,md}`
  - `canonical_entity_map_from_override.json`
  - `capture_manifest.json`

## Populated CANONICAL_ENTITY_MAP Verification

- Verified `request_002_bootstrap_chapter_extraction_ch_001.md` contains `CANONICAL_ENTITY_MAP:` and it is non-empty.
- Verified map contains canonical entries including:
  - `アデルマン・レオフリック`
  - `ティセイア王国`
  - `杖の一族`
  - `ベル`
  - `均衡`
  - `セラ`
- Verified prompt is not the old empty-map form (`CANONICAL_ENTITY_MAP: []`).

## Hardened Contract Still Present

- Recaptured chapter prompt still includes hardened schema/prompt signals:
  - `objects`
  - `CANONICAL_MAP_MODE`
  - `relation_category`
  - `relation_label`
  - `event_importance`

## What To Upload To ChatGPT

- Upload only this file to ChatGPT for next manual response capture:
  - `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260522T163323Z/request_002_bootstrap_chapter_extraction_ch_001.md`

## Provider-free Guarantee

- No provider/API calls.
- No network usage required by this phase logic.
- No secrets used.
- No writes to real `runs/**` or real `vault/**`.
- Private captured prompts remain outside repository in `/tmp`.

## Tests Added / Updated

- Added `tests/test_textifai_real_bootstrap_populated_map_capture_harness.py`.
- Existing harness test suite remained green without modification.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_manual_global_normalization_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_hardened_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_bootstrap_prompt_schema_hardening`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- Real recapture command above
- `git status --short`
- `git diff --stat`

## Data Written

- Code change in dev harness only.
- New provider-free tests.
- New handoff.
- Private recapture artifacts in `/tmp` only.

## Safety Constraints

- Did not modify runtime extraction engine module behavior.
- Did not touch provider runtime code.
- Did not touch chunking or viewer.
- Did not commit private recaptured prompts.
- Did not commit source novel text.

## Known Limitations

- This phase validates prompt recapture only, not model output quality with populated map.
- Override path is dev-only harness behavior, not production provider path.
- Populated-map chapter response comparison remains pending.

## Future Extensions

- Next: manual ChatGPT response on populated-map prompt and comparison versus `SP-052` empty-map hardened sample.
- Then decide readiness for canonical-map-populated e2e checks across more chapters/languages.

## Runtime Changes

- Dev harness only.

## Provider Calls

- No.

## Write-back

- No.

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.M-b5c-2b` — populated-map chapter response manual audit and comparison against `SP-052`.
