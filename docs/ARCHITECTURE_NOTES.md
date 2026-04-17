# Architecture Notes

## Consistency Check Scope

`consistency-check` is a minimum persistence guardrail for the interactive layer.

It helps prevent obvious out-of-context writes before notes are persisted, but it does not replace:

- `editor-review`
- `reader-review`
- a future advanced `consistency-check`

Its current role is intentionally narrow:

- catch clear contradictions against validated lore/canon
- flag high-risk implications that should become canon proposals
- block unsafe writes before they touch the vault

## Context Literality

The Context Engine models literality as a public continuous scale from `0.0` to `1.0`.

- `1.0` means "as literal as possible"
- `0.0` means "as compressed as possible"
- intermediate values mean a gradual tradeoff between literal carry-over and summarization

This setting is applied by artifact type in the builder layer, not in query/selection.
Selection still works on structured candidates; literality only affects how much candidate content is rendered into the final `context_pack`, always subject to section budgets.
