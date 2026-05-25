# Source-ref Carry-forward + Dynamic Output Budget / Continuation Protocol

## Product Reading

`SP-075` validated chunked DeepSeek direction with much stronger reduction scores vs non-chunked baselines, but exposed two robustness gaps: item-level source refs not preserved in final reduction and truncation risk on partial extraction outputs. This phase focuses on protocol robustness instead of blind overlay tuning.

## Scope

Provider-free protocol and runtime-hardening updates:

- source-ref carry-forward merge/fallback rules;
- dynamic output budget resolver;
- output budget prompt injection;
- response_control contract;
- truncation detection upgrades;
- usage/finish_reason capture requirements;
- continuation/repair contract;
- candidate summary budget risk guidance;
- updated tests, reports, docs.

Mini real recheck intentionally not executed in this phase.

## Files Changed

- `textifai/import_review/token_budget.py`
- `textifai/import_review/provider_prompt_profiles.py`
- `textifai/import_review/deepseek_family_profiles.py`
- `textifai/import_review/prompt_experiment_observability.py`
- `textifai/import_review/chunking_reduction_preflight.py`
- `scripts/dev/real_deepseek_e2e_dryrun.py`
- `tests/test_textifai_chunking_reduction_preflight.py`
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/test_textifai_prompt_experiment_observability.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/output_budget_capability_resolver_after_sp075.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/response_control_contract_after_sp075.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/continuation_repair_contract_after_sp075.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/source_ref_carry_forward_after_sp075.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/truncation_detection_after_sp075.json`
- `docs/textifai-provider-run-decision-packets.md`
- `docs/textifai-chunking-reduction-preflight.md`
- `docs/textifai-output-budget-continuation-protocol.md`
- `docs/handoffs/safepoint-076_source-ref-carry-forward-output-budget-continuation.md`

## Source-ref Carry-forward

Added provider-free carry-forward behavior:

- preserve incoming `source_refs` from partial items;
- add chunk-level fallback refs when missing;
- merge refs across contributing chunks;
- dedupe refs by source/chapter/chunk/span tuple;
- keep review/local_candidate semantics unchanged.

## Dynamic Output Budget Resolver

Added `resolve_effective_output_budget` with explicit decision order:

1. CLI override;
2. user/config override;
3. profile default;
4. model registry;
5. provider default.

Resolved metadata includes decision source and effective token cap for run-level audit.

## Output Budget Prompt Injection

Added idempotent budget control injection block in provider profile prompt assembly:

- dynamic token budget value from resolver;
- partial completion contract via `response_control`;
- no hardcoded universal 8192 outside profile/registry defaults.

## Response Control Contract

Added provider-free contract fixture and helper-backed structure:

- `completion_status`, `continuation_required`, `continuation_cursor`, `omitted_sections`, part index metadata;
- legacy outputs without response_control remain allowed.

## Truncation Detection

Extended failure taxonomy and classifier signals:

- `finish_reason_length`;
- `output_near_max_tokens`;
- `unterminated_string`;
- `unterminated_array_or_object`;
- keeps `invalid_json_unknown` fallback when no safe truncation signal exists.

## Usage / Finish Reason Capture

Updated `scripts/dev/real_deepseek_e2e_dryrun.py` to write per-call:

- `provider_usage.json`;
- `finish_reason_report.json`;
- effective output budget trace in request metadata and public summary rows.

## Continuation / Repair Contract

Added provider-free continuation contract fixture:

- trigger conditions from partial/truncation signals;
- same provider/model/profile safety rule unless user allows otherwise;
- merge and dedupe source refs;
- no duplicate item replay;
- private packet trace required.

## Candidate Summary Budget Risk

Added chunk prompt guidance:

- keep `candidate_summary_points` short/optional;
- prioritize structured sections over long prose.

## Mini Real Recheck

Not executed in this phase. Reason: phase objective prioritized protocol hardening and provider-free validation. Suggested next phase includes targeted mini real recheck under strict call cap.

## Private Decision Packet

No new provider run in this phase. Existing SP-075 packet remains reference baseline.

## What Is Ready

- source-ref carry-forward rules + dedupe;
- dynamic output budget resolver with source-of-decision;
- output budget prompt injection;
- response control contract;
- truncation detection taxonomy/signals;
- continuation/repair contract;
- usage/finish_reason capture contract in real dryrun script.

## What Still Has Gaps

- no mini real recheck yet to empirically validate new continuation protocol on live DeepSeek output;
- item-level source-ref persistence still needs live verification in next controlled run.

## Tests Added / Updated

- `tests/test_textifai_chunking_reduction_preflight.py`
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/test_textifai_prompt_experiment_observability.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`

## Validation Performed

Full required unittest suite passed.

## Safety Constraints

- No OpenAI.
- No auto-switch.
- No write-back.
- No `/tmp` commit.
- No private prompt/output commit.

## Known Limitations

Provider-free protocol is ready, but continuation behavior still lacks fresh live-run confirmation under SP-076 changes.

## Future Extensions

- run mini real recheck with cap <= 4 calls;
- verify item-level source refs in reduced output;
- verify truncation/continuation trigger behavior from real finish_reason + usage.

## Runtime Changes

Dev/runtime script and protocol helpers updated; no product schema migration beyond additive protocol fields.

## Provider Calls

NO (this phase).

## Write-back

NO.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4f — Mini Real DeepSeek Recheck for Source Refs and Truncation Recovery`

## Assessment

`source_refs_ready_continuation_protocol_partial`
