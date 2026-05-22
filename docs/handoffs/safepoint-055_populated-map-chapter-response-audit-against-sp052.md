# Populated Canonical Map Chapter Response Audit Against SP052

## Product Reading

- `safepoint-052` proved hardened chapter extraction works better with empty `CANONICAL_ENTITY_MAP`.
- `safepoint-053` stored manual global normalization and produced a non-empty canonical map with real builder code.
- `safepoint-054` recaptured real chapter extraction prompt with populated `CANONICAL_ENTITY_MAP`.
- This phase stores manual ChatGPT response for that populated-map prompt and compares it against `SP-052`.
- No runtime change, provider/API call, chunking, write-back, merge, promote, or canon mutation was performed.

## Scope

- Store populated-map manual ChatGPT response sample for Japanese `ch_001`.
- Add checklist, comparison report, and populated-map issue report.
- Add provider-free test covering schema, v2 contract, canonical reuse, coverage, improvements vs `SP-052`, and safety.
- Update provider samples README.
- Create this handoff.

## Files Changed

- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/populated_map_chapter_response_schema_checklist.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/sp052_vs_populated_map_response_comparison_report.json`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/expected/bootstrap_populated_map_issue_report_after_sp054.json`
- `tests/test_textifai_real_bootstrap_populated_map_chatgpt_response_audit.py`
- `tests/fixtures/textifai/real_novel/real_bootstrap_prompt_capture/provider_samples/README.md`
- `docs/handoffs/safepoint-055_populated-map-chapter-response-audit-against-sp052.md`

## Populated Captured Prompt Used

- Prompt source: real capture from `safepoint-054`.
- Path used by user: `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260522T163323Z/request_002_bootstrap_chapter_extraction_ch_001.md`.
- Prompt contained populated `CANONICAL_ENTITY_MAP` and hardened contract fields.
- Prompt itself was not committed.

## ChatGPT Populated-map Response Sample

- Stored sample: `chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_populated_map_after_sp054.json`.
- Manual ChatGPT response only.
- Not provider runtime output.
- Not canon approval.

## Schema Validation

- JSON parseable.
- Top-level contains `work` and `chapters`.
- `work.title == "王者の杖"` and `work.language == "ja"`.
- Chapter identity remains `ch_001`, title `**（仮）証人**`, canonical title `（仮）証人`.

## V2 Contract Validation

- `chapter_extraction_schema_version == "v2"`.
- `objects` exists and includes `object_subkind` and `retention_reason`.
- `events` include `event_importance`.
- `relations` include `relation_category`, `relation_label`, `relation_summary`, and `evidence`.
- Output does not rely on legacy-only `relation_type`.

## Canonical Reuse

- `私` now maps to `証人` while remaining review-gated.
- `舌のないベル` maps to canonical `ベル`.
- `城` maps to `王城`.
- `王妃` maps to `ネリス女王` with review because chapter evidence alone is not enough.
- `赤子` remains descriptor/review.
- `王者の杖` remains tied to `王と杖` under review, not absolute merge.

## Useful Coverage

- Coverage preserved for `アデルマン・レオフリック`, `ティセイア王国`, `杖の一族`, `王と杖` / `王者の杖`, `均衡`, `ベル`, `赤子`, `証人`.
- Events retained: Thiseia collapse, lineage erasure, baby rescue, bell recovery, Adelman regency, hidden upbringing.

## Improvements vs SP052

- Better canonical endpoints for narrator, object, place, and some title aliases.
- Local candidate reliance reduced where canonical map gives safe reuse.
- Relation endpoints improved for `証人`, `ベル`, `杖の一族`, and `アデルマン・レオフリック`.
- Safety preserved for dangerous identity candidates.

## What Worked Better

- Populated map materially improves endpoint normalization.
- `ベル` remains first-class object and canonicalized.
- `証人` helps narrator relations become more useful without false proper-name promotion.
- `王城` improves place normalization.

## What Stayed Weak

- Sample is manual, not provider runtime output.
- Canonical map comes from `ch_001`-`ch_003`, not full novel.
- Multi-chapter populated-map behavior is still untested.
- Spanish/multilingual populated-map behavior is still untested.
- Chunking/reduction path remains unaudited.

## Review / No Auto-promotion Safety

- `私` remains `pronoun_like` and `needs_review: true` despite canonical reuse as `証人`.
- `赤子` remains review-gated.
- `王者の杖` identity remains review-gated.
- `王妃` to `ネリス女王` remains review-gated.
- No auto-promotion or unsafe merge approval appears in sample.

## Remaining Prompt / Schema Issues

- Provider runtime not tested.
- Manual global normalization dependency remains.
- Map scope is limited to first three chapters.
- Downstream object/relation materialization needs later validation.

## Populated Map Result

- Result: `populated_map_improves_resolution_without_auto_promotion`.
- `empty_canonical_entity_map_in_capture` improved/resolved for capture harness audit.

## Objects First-class Result

- `ベル` remains in `objects` with `canonical: ベル`, `object_subkind: ritual_key`, and `retention_reason: event_trigger`.

## Relation Endpoint Result

- Relations use stronger canonical endpoints and keep evidence/review fields.
- Key improvement: `私/証人` and `舌のないベル/ベル` endpoints.

## Event Retention Result

- Event retention remains stable vs `SP-052`.
- Dense chapter still retains major/supporting event priority.

## Provider-free Guarantee

- No provider/API calls.
- No network needed.
- No secrets used.
- Tests read versioned JSON and docs only.
- No write-back to `runs/**` or `vault/**`.

## Tests Added / Updated

- Added `tests/test_textifai_real_bootstrap_populated_map_chatgpt_response_audit.py`.
- Updated provider samples README.
- Added three expected report/checklist fixtures.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_manual_global_normalization_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_hardened_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_bootstrap_prompt_schema_hardening`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_prompt_capture_harness`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `git status --short`
- `git diff --stat`

## Data Written

- Manual populated-map response JSON sample.
- Checklist JSON.
- Comparison report JSON.
- Issue report JSON.
- Provider-free test.
- Handoff.

## Safety Constraints

- No runtime code touched.
- No capture harness touched.
- No provider code touched.
- No chunking/viewer code touched.
- No private prompt captured into repo.
- No source novel text committed.

## Known Limitations

- Manual sample may be cleaner than provider runtime output.
- Map is not full-novel map.
- Downstream UI/import behavior still not audited.

## Future Extensions

- Multi-chapter populated-map audit.
- Spanish populated-map audit.
- Provider-runtime dry run only when approved.
- Chunking/reduction audit after extraction contract proves stable.

## Runtime Changes

- None.

## Provider Calls

- No.

## Write-back

- No.

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

- `Phase 1.3.M-b5c-2c` — multi-chapter populated-map response audit, then chunking/reduction audit gate.
