# Controlled Full-source Dry-run Planning with Fail-only Retry UX Contract

## Product Reading
- SP-083 already proved broader real natural multi-chunk stability (4 chapters, 43 calls, 8/8 valid reductions, source_ref coverage 1.0).
- Product risk now is end-to-end retry loop for writers, not only technical extraction quality.
- SP-084 focuses on contract + planning:
  - detect affected chapters;
  - show simple writer-facing outcome;
  - retry only affected chapters;
  - consolidate final outcome;
  - plan full-source dry-run with cap/cost control.

## Scope
- Provider-free contract hardening for fail-only retry and writer-facing outcome.
- Provider-free rerun execution plan for SP-083 affected chapters (`ch_106`, `ch_115`).
- Provider-free controlled full-source dry-run planning.
- No full-source execution.
- No write-back.
- No OpenAI.

## Files Changed
- `textifai/import_review/chunking_reduction_preflight.py`
- `tests/test_textifai_chunking_reduction_preflight.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_retry_contract_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/writer_facing_ingestion_outcome_contract_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/technical_to_user_status_mapping_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/sp083_fail_only_rerun_execution_plan_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/sp083_fail_only_rerun_consolidated_outcome_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/controlled_full_source_dryrun_plan_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_retry_general_pipeline_learnings_after_sp083.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_retry_deepseek_specific_learnings_after_sp083.json`
- `docs/handoffs/safepoint-084_full-source-planning-fail-only-retry-ux.md`

## SP083 Context
- SP-083 writer-facing outcome:
  - 2 of 4 chapters ready;
  - 2 chapters need second pass (`ch_106`, `ch_115`);
  - CTA `Retry pending chapters`.
- SP-083 internal fail-only rerun plan already marked only affected chapters as retryable.

## Internal Fail-only Rerun Contract
- Added strict internal contract report:
  - `ingestion_run_id`;
  - retryable/non-retryable chapters;
  - retryable units with chapter/run ids, strategy, expected calls;
  - dependency policy excluding successful chapters unless explicit dependency;
  - graph completion before/after retry;
  - consolidation rules.
- Report: `fail_only_retry_contract_after_sp083.json`.

## Writer-facing Ingestion Outcome Contract
- Added writer contract report with explicit allowed states:
  - outcome: `success`, `success_with_warnings`, `success_with_retry_available`, `partial_failure`, `failed`;
  - chapter: `ready`, `ready_with_warnings`, `needs_retry`, `needs_review`, `failed`.
- Added reason labels and fixed CTA contract:
  - primary: `Retry pending chapters` / `retry_pending_chapters` / `affected_chapters_only`;
  - secondary: `Later` / `dismiss`.
- Report: `writer_facing_ingestion_outcome_contract_after_sp083.json`.

## Technical-to-User Status Mapping
- Added deterministic rule map from technical signals to writer statuses.
- Rules cover:
  - valid+clean -> `ready`;
  - valid+warnings -> `ready_with_warnings`;
  - retryable failure/low-density -> `needs_retry`;
  - suspicious thinness -> `needs_review`;
  - unrecoverable -> `failed`.
- Report: `technical_to_user_status_mapping_after_sp083.json`.

## SP083 Fail-only Rerun Execution Plan
- Provider-free rerun plan built strictly for affected chapters only:
  - chapters to retry: `ch_106`, `ch_115`;
  - chapters excluded: `ch_097`, `ch_114`.
- Planned calls:
  - base: 15;
  - continuation reserve: 8;
  - total: 23;
  - cap: 24;
  - fits cap: true.
- Report: `sp083_fail_only_rerun_execution_plan_after_sp083.json`.

## Optional Real Fail-only Rerun
- Not executed in SP-084 (contract/planning phase only).
- Status recorded as `not_executed_contract_only`.
- If executed later, must stay scoped to affected chapters only and use private packet root:
  - `/tmp/textifai_private_provider_runs/sp084_fail_only_retry_contract/<timestamp>/`.

## Consolidated Outcome After Retry
- Added simulated consolidated outcome contract (no fake success):
  - preserves previous SP-083 outcome;
  - defines what updates after retry;
  - includes best-case and partial-success branches.
- Report: `sp083_fail_only_rerun_consolidated_outcome_after_sp083.json`.

## Controlled Full-source Dry-run Plan
- Added provider-free full-source plan (no execution):
  - estimated chapters: 117;
  - estimated calls (with reserve):
    - flash-only: 361;
    - flash+pro: 723.
  - proposed staged cap: 96 per batch;
  - phased execution A/B/C with stop conditions and fail-only retry after each phase;
  - no automatic write-back.
- Report: `controlled_full_source_dryrun_plan_after_sp083.json`.

## General Pipeline Learnings
- Core reusable capabilities:
  - fail-only retry contract;
  - writer-facing outcome contract;
  - technical-to-user mapping;
  - retry CTA and affected-only scope;
  - consolidated outcome rules;
  - staged full-source planning.
- Report: `fail_only_retry_general_pipeline_learnings_after_sp083.json`.

## DeepSeek-specific Learnings
- Keep provider-specific:
  - Flash/Pro retry strategy hints;
  - Pro low-density handling with compact reduction hint;
  - reasoning pressure signals;
  - DeepSeek wrong-chapter continuation pattern.
- Report: `fail_only_retry_deepseek_specific_learnings_after_sp083.json`.

## Private Decision Packet
- No new real rerun executed in SP-084.
- Private packet path reserved for optional execution:
  - `/tmp/textifai_private_provider_runs/sp084_fail_only_retry_contract/<timestamp>/`.

## Product Decision
- `fail_only_retry_contract_ready_with_review_warnings`

## What Worked
- Retry scope contract now excludes successful chapters by default.
- Writer-facing contract standardized with stable CTA.
- Deterministic mapping rules documented and tested.
- Full-source dry-run now has cap/cost-aware staged plan.

## What Failed
- No live retry execution in this phase (intentional by scope).
- Full-source cost remains high if Flash+Pro is applied uniformly.

## Data Written
- New SP-084 privacy-safe reports under `tests/fixtures/textifai/real_provider_dryrun/expected/`.
- New SP-084 handoff doc.

## Privacy / Non-committed Output
- No `/tmp` committed.
- No prompts/raw provider outputs committed.
- No API keys committed.
- No source prose committed.

## Tests Added / Updated
- Added provider-free helper tests for SP-084 contracts in `tests/test_textifai_chunking_reduction_preflight.py`.
- Added SP-084 guards for report parsing, retry scope, writer-term filtering, consolidated outcome, and full-source planning in `tests/test_textifai_real_provider_dryrun_guards.py`.

## Validation Performed
- Full required unittest suite executed.
- Optional real rerun skipped by design in this phase.

## Safety Constraints
- No OpenAI.
- No auto-switch invisible.
- No write-back.
- No full-source execution.
- Optional rerun not executed.

## Known Limitations
- Consolidated outcome in SP-084 is simulation contract only.
- Writer-facing contract is report-level; no UI runtime integration yet.

## Future Extensions
- Execute optional real fail-only rerun (`ch_106`, `ch_115`) under cap 24.
- Integrate outcome contract with actual ingestion UX.
- Run staged full-source dry-run Phase A with strict stop conditions.

## Runtime Changes
- Added provider-free helpers for:
  - fail-only retry contract;
  - writer-facing outcome contract;
  - technical-to-user mapping;
  - SP-083 rerun execution planning;
  - controlled full-source dry-run planning.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- Phase 1.3.M-b5c-4n — Execute SP083 fail-only rerun (`ch_106`, `ch_115`) under cap 24, then run controlled full-source Phase A.
