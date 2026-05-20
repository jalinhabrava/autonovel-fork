# Safe Fixtures and Baselines

## Purpose

TextifAI needs reproducible validation fixtures for semantic work because semantic output can change without code crashes.

Runs and vault artifacts may be valuable, expensive to regenerate, or useful as historical comparability evidence. They must not be casually overwritten, normalized, regenerated, or cleaned.

Real novel data may be large, private, unstable, or unsuitable for tests. It may also include author-specific naming, lore, draft state, or editorial intent that should not become general-purpose test material.

Semantic contract changes need controlled comparison so future reviewers can distinguish expected output changes from accidental regressions.

## Fixture Principles

Fixtures must be:

- small
- deterministic
- non-private
- committed intentionally
- safe to regenerate
- designed to cover specific pipeline features
- never copied blindly from real user vaults or runs unless sanitized and approved

A fixture should have a clear purpose. Avoid large fixture blobs that are hard to understand or update.

## Proposed Fixture Classes

### Minimal Novel Fixture

Purpose:

- chapter detection
- entity extraction shape
- basic Obsidian import shape
- deterministic slugs/chapter refs

Should contain:

- 2-3 short chapters
- 2 recurring characters
- 1 place
- 1 object
- 1 relationship
- 1 alias/variant naming case

### Semantic Edge Fixture

Purpose:

- canonicalization
- merge/review boundaries
- confidence thresholds
- aliases
- conflicting facts

Should contain:

- similar but distinct names
- uncertain identity
- repeated concept label
- relationship ambiguity

### VaERL Fixture

Purpose:

- validate entity/relation invariants
- resolver behavior
- review queue behavior

Should contain:

- expected canonical entities
- expected unresolved/review candidates
- expected relation patterns

### Obsidian Import Fixture

Purpose:

- note layout
- generated filenames
- `99_System` artifact shape
- `obsidian_import.json` shape

Should contain:

- known expected note outputs
- expected filenames/slugs
- expected metadata blocks

## Proposed Directory Layout

Suggested future layout, not created in this phase:

- `tests/fixtures/textifai/minimal_novel/`
- `tests/fixtures/textifai/semantic_edges/`
- `tests/fixtures/textifai/vaerl/`
- `tests/fixtures/textifai/obsidian_import/`
- `tests/snapshots/textifai/`

Do not create these directories without explicit approval in a future phase.

## Baseline Strategy

A baseline is an expected output snapshot from a known-good command/version.

Baselines should be:

- tied to a fixture and command
- small enough to review
- committed intentionally
- updated only with explicit approval
- accompanied by notes explaining expected differences

Baseline updates must state semantic contract changes YES/NO.

Artifact diffs must distinguish expected changes from accidental changes.

No baseline should be generated from real user `runs/` unless explicitly approved.

## Artifact Diff Strategy

When validating semantic changes, compare contract-relevant fields instead of only checking command success.

Compare:

- entity count
- canonical names
- slugs
- aliases
- relationships
- `review_state`
- `chapter_refs`
- generated filenames
- note headings
- `obsidian_import.json` shape
- VaERL invariant results
- review queue entries

Prefer structured diffs for JSON and concise summaries for Markdown/vault outputs.

## Future Fixture Creation Plan

Future phase:

`Phase 0.5 — Create Minimal Fixture Harness`

Potential scope:

- create fixture directory
- add tiny synthetic novel
- add expected baseline docs/json
- add one targeted test or script if appropriate

Do not implement this now.

## Preservation Rules

- never write test outputs into real `runs/`
- never write test outputs into real `vault/`
- use temporary directories or dedicated fixture output dirs
- generated fixture outputs must be clearly separated from user artifacts
- any generated baseline update requires approval

If a semantic validation command can write by default, choose an explicit temporary or fixture output location before running it.

## Handoff Requirements

Every semantic validation handoff must state:

- fixture used
- command run
- output location
- baseline compared
- expected differences
- unexpected differences
