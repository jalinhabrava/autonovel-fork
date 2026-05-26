# Execute SP083 Fail-only Rerun and Consolidated Writer Outcome

## Product Reading
- SP-083 already validated broader natural multi-chunk run and produced a writer-facing retry need on `ch_106` and `ch_115`.
- SP-084 hardened provider-free contracts for fail-only retry, writer-facing outcomes, technical-to-user mapping, and full-source planning.
- SP-085 executes the real retry loop for affected chapters only, then consolidates final writer-facing outcome.

## Scope
- Real provider fail-only rerun only for `ch_106` and `ch_115`.
- Excluded successful chapters `ch_097` and `ch_114`.
- No full-source execution.
- No OpenAI, no auto-switch, no write-back.

## Files Changed
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `docs/handoffs/safepoint-085_fail-only-rerun-live-consolidated-outcome.md`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_execution_plan_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_internal_results_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_consolidated_outcome_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_writer_outcome_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/full_source_phase_a_readiness_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_general_pipeline_learnings_after_sp084.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/fail_only_rerun_live_deepseek_specific_learnings_after_sp084.json`

## SP084 Context
- Provider-free plan from SP-084 set retry scope to `ch_106`, `ch_115`.
- Planned calls: 23 under cap 24.
- Retry contract required strict exclusion of successful chapters.

## Retry Scope
- Retried chapters: `ch_106`, `ch_115`.
- Excluded chapters: `ch_097`, `ch_114`.
- No extra chapters included.

## Execution Plan
- Plan report: `fail_only_rerun_live_execution_plan_after_sp084.json`.
- Planned calls:
  - partial base calls: 11
  - reduction base calls: 4
  - continuation reserve: 8
  - planned total: 23
  - cap: 24
  - fits cap: true

## Provider Calls
- Real provider calls executed: 19.
- Cap respected: 19 <= 24.
- DeepSeek only.

## Long-run Handling
- Incremental progress log recorded in private packet.
- Per-call duration, output file size, finish status, and failure mode captured.
- Pro calls were not canceled for latency.

## Runtime Results
- 4/4 final reductions parseable and valid for retried scope.
- Source-ref coverage stayed 1.0.
- Continuation triggered on reduction steps and recovered via patch merges.
- No continuation problem count in final audit.

## Internal Retry Results
- Report: `fail_only_rerun_live_internal_results_after_sp084.json`.
- `ch_106`: retry succeeded strongly (Flash 108.5, Pro 107.0).
- `ch_115`: retry improved strongly (Flash 104.0, Pro 76.5) with remaining low-density warning.
- Wrong-chapter merge count remained 0.

## Consolidated Outcome After Live Retry
- Report: `fail_only_rerun_live_consolidated_outcome_after_sp084.json`.
- Before retry (SP-083): ready 2, retry 2.
- After retry (SP-085):
  - ready: 3
  - needing retry: 0
  - needing review: 1 (`ch_115`)
  - failed: 0
- Graph status: `complete_with_review_warnings`.

## Writer-facing Outcome After Live Retry
- Report: `fail_only_rerun_live_writer_outcome_after_sp084.json`.
- Writer-facing summary: “4 chapters processed. 3 are ready. 1 needs review.”
- No internal technical terms exposed.
- Primary action switches from retry CTA to continuation/review CTA when retry backlog is zero.

## Technical-to-User Status Mapping
- Mapping contract from SP-084 respected:
  - resolved chapter -> `ready`
  - valid chapter with remaining semantic concern -> `needs_review`
- No provider/model terms shown in writer-facing report.

## Full-source Phase A Readiness
- Report: `full_source_phase_a_readiness_after_sp084.json`.
- Fail-only retry executed: yes.
- Consolidated outcome acceptable: yes.
- Recommended Phase A: staged run, cap 96, Flash-first then targeted Pro, fail-only retry after phase.
- Full-source still not executed in SP-085.

## General Pipeline Learnings
- Affected-only retry loop works live.
- Successful chapters can be excluded reliably.
- Consolidated writer outcome can update without full rerun.
- Retry CTA can clear backlog while preserving no-write-back safety.

## DeepSeek-specific Learnings
- Flash handled both retried chapters with high-quality reductions.
- Pro compact reduction + patch continuation remained useful.
- `ch_115` Pro still showed low-object density warning, mapped to review path instead of forced retry.

## Private Decision Packet
- Root: `/tmp/textifai_private_provider_runs/sp085_fail_only_rerun_live/20260526T070331Z`
- Kept private and uncommitted.

## Product Decision
- `fail_only_rerun_passed_with_review_warnings`

## What Worked
- Retry scope strict to affected chapters.
- Cap 24 respected.
- Retry backlog cleared (0 chapters needing retry).
- Writer-facing outcome remained simple and safe.

## What Failed
- One chapter (`ch_115`) still needs review due low-density warning.
- Not yet ready to claim “all chapters fully clean”.

## Data Written
- SP-085 live rerun execution/consolidation/readiness/privacy-safe reports.
- SP-085 handoff document.

## Privacy / Non-committed Output
- No `/tmp` committed.
- No prompts/raw outputs committed.
- No API key committed.
- No source prose committed.

## Tests Added / Updated
- Added SP-085 guard test for:
  - cap <=24,
  - strict retry scope,
  - writer-facing forbidden-term filtering,
  - consolidated no-fake-success,
  - readiness report parsing.

## Validation Performed
- Full required unittest suite run.
- Live fail-only rerun executed under cap with DeepSeek only.

## Safety Constraints
- No OpenAI.
- No auto-switch invisible.
- No write-back.
- No full-source execution.

## Known Limitations
- Scope is still only 4-chapter slice from SP-083 context.
- One chapter remains review-needed.

## Future Extensions
- Execute controlled full-source Phase A (staged cap).
- Keep fail-only retry post-phase.
- Optionally refine low-density handling policy for Pro on review chapters.

## Runtime Changes
- No major runtime engine changes in SP-085.
- Focus on live execution of existing fail-only workflow and report consolidation.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- Phase 1.3.M-b5c-4o — Controlled Full-source Phase A (staged cap 96, Flash-first, fail-only retry closeout).
