# Bootstrap V1 Flow

This repository now treats bootstrap as a narrow, auditable pipeline:

1. ingest source documents
2. prefer Markdown as the primary V1 input
3. split long narrative documents into real chapters
4. run one structured LLM extraction per chapter
5. merge likely duplicate entities across chapter JSON outputs
6. build canonical primary notes from the merged entities
7. write chapter notes and chapter summaries with Obsidian links
8. keep unresolved material in hidden review/staging, outside normal retrieval

## Product Direction

The current V1 direction is intentionally simpler than the older staging-heavy flow.

We want:

- chapter-first extraction
- strict JSON outputs
- explicit entity merge passes
- canonical primary notes
- a review bucket for unresolved material

We do not want:

- language-specific semantic heuristics as the main logic
- oversized bootstrap ontologies
- review material polluting the visible graph
- retrieval depending on weak provisional notes

## Canonical Vault Layers

Visible canonical layers:

- `02_World/Places`
- `02_World/Magic`
- `02_World/Creatures`
- `02_World/Factions`
- `02_World/Objects`
- `02_World/History`
- `02_World/Lore`
- `03_Characters/Profiles`

Story grounding layers:

- `04_Story/Chapters`
- `04_Story/Chapter_Summaries`

Hidden internal layers:

- `90_Review`
- `99_Import_Staging`
- `99_System`

## Note Roles

Minimum note roles:

- `primary`
- `chapter`
- `chapter_summary`
- `review`

Minimum review states:

- `canonical`
- `review`

## Graph And Retrieval Policy

The useful narrative graph should show canonical primaries by default.

These tags are reserved for hiding non-canonical or operational notes:

- `#system`
- `#review`
- `#chapters`

Normal retrieval should prioritize:

1. canonical primary notes
2. closely related canonical primaries
3. chapter summaries
4. chapter notes

Review and staging should only be used in explicit review flows.

## Validation Standard

Every bootstrap iteration should leave auditable artifacts when possible:

- extraction audit
- chapter map audit
- chapter processing progress log
- chapter analysis audit
- primary update audit
- retrieval audit

## Current Honest Constraint

The repository already supports chapter-first bootstrap structure, but the next critical step is to make chapter analysis produce reliable primary updates from the manuscript itself, not mainly from auxiliary character/lore documents.
