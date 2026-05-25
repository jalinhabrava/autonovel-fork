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
