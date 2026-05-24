# Execute Profiled DeepSeek ch_002 Dry-run + Density Decision

## Product Reading
- `SP-062` left profiled DeepSeek runtime blocked by environment visibility in that prior session.
- This phase re-checked whether Codex could see `DEEPSEEK_API_KEY`, recaptured local prompt when missing, and executed one guarded profiled DeepSeek call.
- Result: profile applied, but DeepSeek V4 Flash returned non-parseable JSON, so density did not improve and runtime reliability regressed versus generic `SP-060`.

## Scope
- Verify branch and environment.
- Verify or recapture prompt capture availability.
- Execute exactly one profiled DeepSeek call once all guards passed.
- Produce safe summary reports, comparison reports, tests, and handoff without committing private prompt/output.

## Files Changed
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_runtime_summary_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_vs_generic_report_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_profiled_vs_sp056_baseline_report_after_sp062.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_provider_profile_runtime_issue_report_after_sp062.json`
- `docs/handoffs/safepoint-063_execute-profiled-deepseek-ch002-dryrun-density-decision.md`

## Environment Check
- `DEEPSEEK_API_KEY present: True`
- `DEEPSEEK_API_KEY len: 35`
- `DEEPSEEK_API_KEY starts: sk-6fd`
- `DEEPSEEK_API_KEY ends: e7f0`
- `DEEPSEEK_API_KEY sha8: 29fc730d`
- Conclusion: provider call permitted under explicit guardrails.

## Prompt Recapture Status
- Initial prompt search returned no local capture.
- Recapture executed with `scripts/dev/capture_bootstrap_prompts.py`.
- New prompt located at `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260524T082129Z/request_003_bootstrap_chapter_extraction_ch_002.md`.
- Status: `recaptured_prompt_to_tmp`.

## Provider Profile Used
- Applied profile: `deepseek-v4-flash:bootstrap_chapter_extraction:v1`
- Mode: `--provider-profile auto`

## Real Provider Call Status
- `executed_one_call_profiled_json_invalid`
- Exactly one provider call executed.

## Output Directory
- `/tmp/textifai_real_provider_dryrun_profiled/20260524T082222Z`

## Runtime JSON Validation
- `provider_profile_applied = true`
- `provider_profile_id = deepseek-v4-flash:bootstrap_chapter_extraction:v1`
- `max_output_tokens = 8192`
- `response_text_chars = 1939`
- `response_parseable_json = false`
- `validation ok = false`
- `provider_response.json` was not written because output did not parse.

## Profiled vs Generic DeepSeek
- `overall_assessment = profile_regressed`
- Generic `SP-060` remained parseable JSON with minimum v2 shape.
- Profiled `SP-063` lost JSON parseability, so no density win could be credited.

## Profiled vs SP056 Manual Baseline
- `overall_assessment = profiled_deepseek_invalid`
- Manual `SP-056` remains richer and valid.
- Profiled DeepSeek runtime could not be semantically compared because output was invalid JSON.

## Semantic Density Decision
- Final decision: current profile overlay should not be accepted as-is.
- Outcome: profiled DeepSeek runtime regressed on JSON reliability before any semantic density gain could be measured.

## What Improved
- Codex environment visibility issue resolved in this session.
- Prompt recapture harness worked and reproduced `ch_002` prompt safely in `/tmp`.
- Profile application was confirmed in runtime manifest.
- Guardrails still enforced one call, `8192` output budget, JSON mode, no write-back, `/tmp`-only output.

## What Stayed Weak
- Output failed JSON parsing.
- No contract sections could be validated from profiled output.
- No trustworthy semantic density comparison could be made against `SP-060` or `SP-056` beyond regression on parseability.

## Provider Profile Result
- Provider profile infrastructure works mechanically.
- Current DeepSeek density overlay likely interacts poorly with DeepSeek V4 Flash JSON reliability.
- Next iteration should shrink or restructure overlay before another single-call runtime attempt.

## Data Written
- Summary fixtures, comparison reports, updated tests, and handoff.
- Real provider output stayed only under `/tmp/textifai_real_provider_dryrun_profiled/20260524T082222Z`.

## Privacy / Non-committed Output
- No private prompt committed.
- No private provider output committed.
- No API key stored in fixtures or docs.

## Tests Added / Updated
- Updated `tests/test_textifai_real_provider_dryrun_guards.py` to assert executed-profiled-invalid-JSON state for `after_sp062` reports.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `uv run python -m unittest -v tests.test_textifai_provider_onboarding`

## Safety Constraints
- Exactly one provider call.
- No OpenAI.
- No DeepSeek Pro.
- No chunking.
- No write-back.
- No `/tmp` artifacts committed.

## Known Limitations
- One provider/model only.
- One chapter only.
- No valid profiled JSON exists for density comparison.
- No DeepSeek Pro comparison.
- No OpenAI runtime comparison.
- No chunking yet.

## Future Extensions
- Reduce or restructure DeepSeek density overlay into more JSON-safe form.
- Re-run one profiled DeepSeek `ch_002` call after overlay revision.
- If Flash still regresses, compare compact Flash overlay vs `deepseek-v4-pro` or OpenAI runtime in later approved phases.

## Runtime Changes
- Reports only.
- No product runtime changes.

## Provider Calls
- YES, one guarded call.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3h — Compact DeepSeek Overlay Revision Before Second Profiled Runtime Attempt`
