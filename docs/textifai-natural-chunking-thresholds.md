# TextifAI Natural Chunking Thresholds

## Purpose

Natural chunking should split chapters not only when they no longer fit hard context, but also when splitting improves extraction quality, reduction robustness, and source-ref traceability.

## Hard vs Soft Limits

- `hard_max_source_tokens`: absolute safety ceiling derived from context window, prompt overhead, output reserve, and safety margin.
- `soft_chunk_target_tokens`: preferred chunk size for reliable extraction quality.
- `soft_chunk_max_tokens`: recommended upper bound before quality-driven split, even if chapter still fits hard context.
- `min_chunk_tokens`: floor that avoids absurdly tiny chunks.
- `preferred_overlap_paragraphs`: optional overlap carried into semantic splits.

## Split Reasons

- `chapter_within_budget`
- `soft_quality_split`
- `hard_budget_split`
- `heading_boundary_split`
- `paragraph_boundary_split`

## Core vs Provider-specific

General TextifAI core:

- hard vs soft split distinction;
- chunk metadata and stable chunk ids;
- source spans and predecessor/successor links;
- source-ref carry-forward;
- patch continuation chapter validation;
- thin/no-item reduction diagnostics;
- provider-free replan simulation.

Provider-specific suggestions:

- model/profile soft threshold hints;
- compact reduction recommendation;
- reasoning-token risk heuristics;
- provider-specific prompt/profile wording.

## Provider Preference Hook

Providers may suggest chunking preferences, but core planner decides:

```json
{
  "provider_family": "deepseek",
  "model": "deepseek-v4-pro",
  "task": "bootstrap_chapter_extraction",
  "chunking_preferences": {
    "soft_chunk_target_tokens": 1100,
    "soft_chunk_max_tokens": 1700,
    "min_chunk_tokens": 450,
    "compact_reduction_recommended": true
  }
}
```

User/config overrides remain stronger than provider suggestions.

## Threshold Calibration

Use real chapter telemetry to answer:

- why chapters stayed single-chunk;
- what threshold would produce 2 chunks or 3 chunks;
- where over-splitting risk starts;
- which chapters are best for small real validation.

Calibration should not force product defaults blindly. It should produce a provider-free recommendation first, then a targeted validation plan.
