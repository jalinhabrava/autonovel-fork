# Pro Compact Reduction + Patch-based Continuation Recovery

## Product Reading
- SP-077 validated real DeepSeek E2E with warnings: best score 59, dynamic budget, usage/finish_reason, and item-level source_refs on parseable reductions.
- Failure localized to ch_001 + deepseek-v4-pro + reduction: finish_reason=length, 8192/8192 completion tokens, open continuation did not recover parseability.
- SP-078 targets Pro reduction verbosity/reasoning exhaustion with compact reduction and patch-based continuation, not larger E2E.

## Scope
- Added provider-free compact reduction policy and caps.
- Added patch-based continuation contract and merge logic.
- Added finish_reason=length / reasoning budget strategy.
- Ran mini real recheck on ch_001 + deepseek-v4-pro only.
- No OpenAI, no auto-switch, no write-back.

## Files Changed
- scripts/dev/real_deepseek_e2e_dryrun.py
- textifai/import_review/deepseek_family_profiles.py
- textifai/import_review/provider_prompt_profiles.py
- textifai/import_review/prompt_experiment_observability.py
- tests/test_textifai_real_provider_dryrun_guards.py
- tests/test_textifai_prompt_experiment_observability.py
- tests/fixtures/textifai/real_provider_dryrun/expected/*sp077*.json
- docs/handoffs/safepoint-078_pro-compact-reduction-patch-continuation.md

## SP077 Failure Analysis
- Failing case: ch_001 / deepseek-v4-pro / reduction.
- finish_reason: length.
- completion tokens: 8192/8192.
- continuation mode: open repair/full reconstruction; result not parseable.
- response_control absent; runtime must not rely on it as source of truth.

## Pro Compact Reduction Mode
- mode: pro_compact_reduction_v1
- compact mode used in mini recheck: True
- goal: valid compact JSON, item-level source_refs, no long prose.

## Section / Item Caps
- caps: {"max_facts_per_item": 2, "max_evidence_entries_per_item": 1, "max_candidate_summary_points": 0, "max_unresolved_mention_note_chars": 120, "max_relation_summary_chars": 140, "max_event_summary_chars": 160}
- summary points capped to zero; evidence/facts limited.

## Patch-based Continuation
- Patch continuation requested only small `continuation_patch`, not full JSON reconstruction.
- Patch merged into fallback reduction using partial signals and chunk source spans.
- continuation status: patch_merged

## Finish Reason Length Strategy
- finish_reason=length marks output budget exhausted.
- Pro + high reasoning ratio marks pro_reasoning_budget_exhaustion.
- strategy prefers compact retry / patch continuation, same model/profile.

## Reasoning Budget Exhaustion
- reduction reasoning ratio: 0.927734375
- pro_reasoning_budget_exhaustion: True

## Response Control Runtime Policy
- response_control requested but advisory.
- Missing response_control is logged, not failure.
- Runtime uses finish_reason, usage, parseability, tail shape, token ratio.

## Mini Real Recheck
- source: /home/david/OnT/王者の杖.md
- chapter: ch_001 only.
- model/profile: deepseek-v4-pro / deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1
- calls: 3 / 6 cap.

## Runtime Results
- assessment: pro_compact_reduction_recovery_ready
- reduction parseable: True
- reduction validation_ok: True
- score: 30.0
- finish_reason: length

## Truncation Recovery
- compact reduction still hit length, but patch continuation merged.
- continuation_problem_count: 0
- triggered_continuation_count: 1

## Source-ref Audit
- item-level source_ref coverage: 1.0
- missing source_ref runs: 0
- sections: {"characters": {"items": 4, "with_source_refs": 4}, "places": {"items": 4, "with_source_refs": 4}, "concepts": {"items": 4, "with_source_refs": 4}, "objects": {"items": 2, "with_source_refs": 2}, "events": {"items": 4, "with_source_refs": 4}, "relations": {"items": 1, "with_source_refs": 1}, "unresolved_mentions": {"items": 3, "with_source_refs": 3}}

## Private Decision Packet
- root: /tmp/textifai_private_provider_runs/sp078_pro_compact_reduction_patch_continuation/20260525T124450Z
- key files:
  - README.md
  - compact_reduction_policy_private.md
  - patch_continuation_trace_private.md
  - truncation_recovery_audit_private.md
  - source_ref_audit_private.md
  - decision_notes_private.md
  - per-call final_prompt_sent.md / provider_response_raw.txt / provider_usage.json / finish_reason_report.json
- upload first to ChatGPT:
  1. decision_notes_private.md
  2. truncation_recovery_audit_private.md
  3. source_ref_audit_private.md
  4. patch_continuation_trace_private.md
  5. reduction_trace_private.md

## Product Decision
- pro_compact_reduction_recovery_ready

## What Worked
- Compact + patch recovered parseable/valid final reduction for previous problematic case.
- Source refs reached 1.0 coverage.
- Reasoning exhaustion detected without relying on response_control.

## What Failed
- Compact Pro still exhausted budget at reduction call.
- Recovery depends on valid/usable partial extraction and patch merge fallback.

## Data Written
- Privacy-safe fixtures in tests/fixtures/textifai/real_provider_dryrun/expected.
- Private packet in /tmp only.

## Privacy / Non-committed Output
- No prompts/outputs private committed.
- No /tmp committed.
- No API key committed.

## Tests Added / Updated
- Provider-free tests for report privacy, patch merge/source_refs, reasoning exhaustion enum.

## Validation Performed
- Full required unittest suite run in safepoint execution.

## Safety Constraints
- No OpenAI.
- No auto-switch.
- Same model/profile for recovery.
- Max 6 provider calls.

## Known Limitations
- Compact mode can still hit length due high reasoning tokens.
- Patch continuation may produce empty patch if recovery context lacks enough structure.

## Future Extensions
- Reduce Pro reasoning/output pressure before reduction.
- Add smaller reduction prompt or section-wise reductions for Pro.

## Runtime Changes
- Dev script supports compact Pro reduction and patch-based continuation flags.
- Failure classifier includes pro_reasoning_budget_exhaustion.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4h — Larger DeepSeek E2E with Multi-chunk Chapters
