# Entity Fiche Semantic Contract

## Scope
This contract defines how entity fiche data is split before any future write-back.
It applies to graph inspector surfaces, entity-card payloads, generated default fiche bodies, and later semantic reanalysis.

## Layer model

### 1. Structured / calculated layer
These values are rendered outside MDX in compact cards, chips, counters, or technical panels.
Examples:
- aliases
- relationships
- backlinks
- outgoing links
- evidence counts
- graph stats
- technical paths
- review state summaries

This layer is derived data. It is never duplicated into the author-editable MDX body by default.

### 2. Editorial MDX body
This is author-facing prose.
It may contain:
- manual notes
- continuity notes
- wikilinks
- free-form editorial context
- future semantic clues

This layer must preserve user text exactly, including wikilinks and punctuation.
Frontmatter may be hidden in the editor surface, but body text must not be rewritten to inject structured cards.

### 3. Technical / debug layer
This is for implementation details only.
It may include:
- source note path
- resolved technical IDs
- markdown section traces
- raw frontmatter snapshot
- local graph diagnostics

It must stay outside the editorial MDX editor.

## Ownership
- Markdown editor owns editorial prose only.
- Graph / canon view owns derived cards and counters.
- ProjectStore write-back will own persistence later.
- VaERL / Graph / Review projections remain read-only for fiche edits in this phase.

## Source priority
Entity fiche body source priority:
1. `entity_card.author_markdown`
2. `entity_markdown_note_body`
3. `generated_author_markdown`
4. `empty_author_placeholder`

Priority meaning:
- Use authored body first.
- Fall back to note body with frontmatter removed.
- Fall back to a generated editorial scaffold if no body exists.
- Final fallback is an empty placeholder.

## Generated default body
Generated/default fiche body must be editorial-only.
It may include a title, kind, summary, and note space.
It must not inject aliases, relationships, backlinks, outgoing links, or evidence cards into the MDX body.
Those values stay in structured cards outside the editor.

## Wikilinks
Wikilinks written by the author must be preserved exactly.
The system may later propose semantic interpretations from them, but it must not silently mutate entity meaning from the write.

Example:
- author writes: `Ren es el interés romántico de [[Sera]].`
- later reanalysis may propose: `Ren -> interés romántico -> Sera`
- this proposal is deferred and review-gated

## Future semantic state
After fiche save, semantic state should eventually move toward a reanalysis-needed state.
Future pipeline shape:
1. fiche MDX save
2. preserve text and wikilinks
3. mark entity semantic state as needs reanalysis
4. later reanalysis extracts semantic patch
5. author reviews and applies patch
6. Graph / Canon / Review projections update

## Non-goals in this phase
- No fiche write-back to ProjectStore
- No VaERL mutation from fiche edits
- No graph regeneration from fiche edits
- No review regeneration from fiche edits
- No silent semantic mutation
