# TextifAI Output Budget and Continuation Protocol

## Product Value

Chunked extraction becomes more reliable when TextifAI knows the effective output budget for each run, tells the model that budget, detects truncation, and can plan continuation/repair without switching provider or losing traceability.

## Dynamic Budget Resolution

Resolution order:

1. CLI override
2. User/config override
3. Provider profile default
4. Model registry capability
5. Provider default

Resolved fields:

- `effective_max_output_tokens`
- `decision_source`
- `provider_profile_id`
- `model_registry_max_output_tokens`
- `profile_default_max_output_tokens`

## Prompt Injection

Inject a single idempotent block:

- maximum output budget for this response;
- return valid JSON even if incomplete;
- use `response_control` rather than truncating mid-string;
- list omitted sections when continuation is required.

## Response Control Contract

```json
{
  "response_control": {
    "completion_status": "complete|partial",
    "part_index": 1,
    "part_count_estimate": 1,
    "continuation_required": false,
    "continuation_cursor": null,
    "omitted_sections": []
  }
}
```

Legacy outputs without `response_control` remain allowed but should be treated as unknown/legacy.

## Truncation Detection

Use multiple signals:

- `finish_reason == "length"`;
- completion tokens near max output budget;
- unterminated string tail;
- unterminated array/object tail;
- generic `invalid_json_truncated` fallback when safe signals support truncation.

## Continuation / Repair

Trigger continuation when:

- `response_control.partial`;
- `invalid_json_truncated`;
- `finish_reason_length`;
- `output_near_max_tokens`.

Rules:

- same provider/model/profile unless user explicitly allows otherwise;
- do not duplicate previous items;
- preserve and merge `source_refs`;
- trace continuation in private packet.

## Source-ref Carry-forward

Final reduced items should carry `source_refs`. If exact item spans are missing, fallback to contributing chunk spans. Merge refs without duplication. Do not change `review_state` or `local_candidate` semantics.

## BYOK

- no OpenAI auto-switch;
- no provider auto-switch;
- same-model rerun or continuation only unless user changes selection.


## Patch Chapter Validation

Patch continuation should not merge only because JSON parses. Before merge:

- `chapter_id` in patch metadata must match expected chapter;
- `continuation_for.chapter_id` must match when present;
- referenced `chunk_id` values must belong to expected chapter;
- mismatches classify as `valid_json_wrong_chapter`;
- rejected patch stays traceable in private packet and privacy-safe reports.

## Thin / No-item Diagnostics

Parseable reductions can still be too thin to help tracing. Diagnostics should record:

- section item counts;
- empty critical sections;
- `valid_reduction_no_items`;
- `valid_reduction_thin_sections`;
- `source_ref_coverage_lower_due_no_items`.

This keeps source-ref coverage interpretation honest when denominator is near zero.
