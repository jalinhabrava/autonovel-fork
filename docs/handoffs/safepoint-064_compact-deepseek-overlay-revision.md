# Compact DeepSeek Overlay Revision

## Product Reading
- `SP-060` proved DeepSeek V4 Flash can return valid JSON with the generic prompt, but semantic density was thin.
- `SP-061` added Provider Prompt Profiles and a DeepSeek density overlay.
- `SP-063` executed one profiled runtime call; profile application worked, but JSON parseability regressed.
- The current problem is overlay calibration, not key, provider, wrapper, prompt capture, or guards.
- Product rule: provider profiles may improve density, but must not sacrifice valid JSON.

## Scope
- Revise DeepSeek V4 Flash overlay provider-free.
- Make overlay compact, imperative, and JSON-first.
- Add explicit profile policy fields for JSON reliability and overlay style.
- Update fixtures, docs, tests, and handoff.
- Do not execute provider/API calls.

## Files Changed
- `textifai/import_review/provider_prompt_profiles.py`
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_bootstrap_chapter_extraction_profile.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_density_prompt_overlay.md`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_compact_json_first_overlay.md`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_overlay_revision_report.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/provider_prompt_profiles_registry_report.json`
- `docs/textifai-provider-prompt-profiles.md`
- `docs/handoffs/safepoint-064_compact-deepseek-overlay-revision.md`

## Previous Profiled Runtime Result
- `SP-063` status: `executed_one_call_profiled_json_invalid`.
- Profile applied: `deepseek-v4-flash:bootstrap_chapter_extraction:v1`.
- Runtime response chars existed, but response was not parseable JSON.
- Assessment: `profile_regressed` vs generic DeepSeek and `profiled_deepseek_invalid` vs `SP-056`.

## Overlay Problem
- Previous overlay was density-first and more verbose.
- It repeated several semantic requirements and likely competed with the main JSON/schema instruction.
- It improved pressure for coverage in theory, but runtime result showed JSON reliability loss.

## Revised Overlay Strategy
- Compact JSON-first overlay.
- Short imperative instructions.
- No examples, no story-specific content, no schema duplication beyond required top-level keys.
- Keep density pressure only for `objects`, `events`, `relations`, and `unresolved_mentions`.

## JSON Reliability First
- New policy: `json_first_no_markdown_single_object`.
- Overlay begins with: return exactly one valid JSON object; do not use markdown.
- This is intentionally prioritized before density language.

## Density Policy
- New policy: `compact_high_recall`.
- Density instruction remains, but compressed:
  - do not compress into summary only;
  - include structurally relevant objects/tools/artifacts/catalysts/weapons;
  - include durable events;
  - include evidence-backed relations;
  - include important unresolved mentions.

## Profile Shape Changes
- Added `json_reliability_policy`.
- Updated `prompt_density_policy` from `high_recall_concise_facts` to `compact_high_recall`.
- Added `overlay_style = compact_json_first`.

## Density Validation Role
- Prompt profile asks for coverage.
- Provider-free validation detects missing sections, thin object/relation/unresolved coverage, and missing importance/category markers.
- Retry/fallback policy remains future work and should choose between compact retry, stronger JSON-safe overlay, DeepSeek Pro, OpenAI, or split/reduction changes.

## Tests Added / Updated
- Tests now assert JSON-first wording, no markdown instruction, required sections, compact length, review safety, OnT-agnostic overlay, idempotent application, policy fields, and parseable reports.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`

## Data Written
- Only provider-free code, fixtures, docs, tests, and handoff.
- No `/tmp` artifacts committed.

## Safety Constraints
- No provider/API call.
- No network use.
- No OpenAI.
- No DeepSeek Pro.
- No chunking.
- No write-back.
- No prompt/output private files committed.

## Known Limitations
- Compact overlay is untested in runtime until next approved phase.
- One DeepSeek Flash profile only.
- Density validation remains heuristic and not semantic diff.
- No product ingestion runtime wiring.

## Future Extensions
- Execute one second profiled DeepSeek `ch_002` call with compact overlay.
- Compare compact overlay against generic `SP-060`, failed profiled `SP-063`, and manual `SP-056`.
- If compact overlay restores JSON but remains thin, decide between profile iteration, `deepseek-v4-pro`, OpenAI, or chunking/reduction work.

## Runtime Changes
- Provider profile overlay only.
- No product ingestion runtime change.

## Provider Calls
- NO.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3i — Second Profiled DeepSeek ch_002 Dry-run with Compact Overlay`
