# TextifAI Semantic Story Engine Roadmap

Status: living roadmap

Last updated: 2026-04-24

## How To Use This Document

This document is a technical-product roadmap for TextifAI. It is not a closed implementation spec, a marketing page, or a checklist to build everything immediately.

Use it to:

- align future work around a shared architecture
- decide the next correct iteration
- mark phases as `not started`, `in progress`, `blocked`, or `done`
- define when one layer is mature enough to build the next one
- keep product direction separate from low-level pipeline docs

Related low-level docs:

- `docs/ARCHITECTURE.md`
- `docs/BOOTSTRAP_V1_FLOW.md`
- `docs/VAULT_SCHEMA.md`
- `docs/e2e_semantic_diagnosis_rules.md`
- `docs/NOVEL_INDEX_AND_SELECTIVE_NORMALIZATION.md`

## 0. Product Thesis

TextifAI is a Semantic Story Engine.

It helps authors turn manuscripts, lore notes, character sheets, future plans, and editorial corrections into a durable semantic model that can support writing, querying, continuity checking, review, and editorial synthesis.

TextifAI is not only:

- a novel importer
- an Obsidian note generator
- a Codex
- a Story Bible
- a chat with AI
- a manuscript editor
- a prompt wrapper around long context

Those are views, workflows, or product surfaces built on top of one shared semantic layer.

The core product bet is:

> VaERL is the semantic source of truth. Every user-facing view should be derived from VaERL or explicitly write back to VaERL through auditable author actions.

This is what should differentiate TextifAI from "another AI editor" or "another Codex":

- It does not rely on the LLM remembering the novel inside a prompt.
- It does not hide canon decisions inside generated prose.
- It separates facts, inference, uncertainty, review state, and author corrections.
- It can replay semantic compilation from frozen artifacts.
- It can support multiple products from one semantic model.

## 1. System Layers

TextifAI must keep these layers distinct.

### 1.1 Semantic Model

VaERL is the source semantic model. It represents what TextifAI knows, how strongly it knows it, where it came from, and whether it is canonical, in review, inferred, or unresolved.

VaERL is not a Markdown folder and not a transient prompt output.

### 1.2 Pipeline Artifacts

Pipeline artifacts are generated JSON files, audits, traces, and intermediate outputs used to build or debug VaERL.

Examples:

- `novel_index.json`
- `global_normalization.json`
- `chapter_outputs/*.json`
- `resolved_entities.json`
- `cleaned_entities.json`
- `auxiliary_source_index.json`
- `auxiliary_extractions/*.json`
- `obsidian_import.json`
- `*_audit.json`
- `run_comparability_manifest.json`

These artifacts are observable boundaries. They are not the product UI.

### 1.3 Persisted Storage

Persisted storage is the durable representation used by humans, tools, and future sessions.

Examples:

- Obsidian vault Markdown
- VaERL snapshots
- bridge snapshots
- JSON import/export payloads
- future database/index representations

Markdown remains a first-class output because authors can inspect, edit, and version it.

### 1.4 Views / User-Facing Projections

Views are projections over VaERL.

Examples:

- Codex View
- Story Bible View
- Review Queue
- Editor / Manuscript View
- Query Layer
- fixed command workflows
- free author chat

Views should not become independent sources of canon unless they write back through explicit, auditable actions.

## 2. VaERL Core

Status: `in progress`

VaERL is the structural base of TextifAI.

It should contain or be able to contain:

- works
- source documents
- chapters
- chapter summaries
- chapter labels
- entities
- canonical names
- preferred slugs
- aliases
- source mentions
- relationships
- relationship facts
- evidence spans
- review states
- confidence
- tags
- entity kinds
- entity subkinds
- relevant events
- unresolved mentions
- audit data
- run comparability metadata
- semantic invariants
- links between chapters and entities
- auxiliary-document facts
- author corrections

VaERL must be:

- auditable
- versionable
- replayable
- consultable
- usable by humans
- usable by LLMs
- stable enough for product views
- flexible enough for review and correction

### 2.1 Semantic Invariants

Initial invariants:

- VaERL is source of truth.
- No hidden canon changes.
- Every view must be derivable from VaERL.
- Canonical entities need stable naming and slugs.
- `preferred_slug` is the internal link target.
- `canonical_name` is presentation/canon naming, not a linking mechanism.
- Review state must remain visible.
- Facts, inference, uncertainty, and author corrections must be distinguishable.
- Author corrections must be traceable.
- Replayability matters.
- Pipeline runs must expose comparability metadata.
- LLM-generated prose must not silently become canon.
- Merge decisions must be auditable.
- Missing evidence should be visible, not papered over.

### 2.2 VaERL Maturity Signals

VaERL is mature enough to support richer product views when:

- primary protagonist and major supporting entities remain stable across comparable runs
- slug/link policy is stable
- language consistency is enforced in semantic artifacts
- review entities are useful instead of noisy dumping grounds
- common merge cases are handled or surfaced cleanly
- downstream replay can validate changes without rerunning extraction
- semantic invariants can be run as tests or audits
- author-facing Markdown is readable enough to inspect manually

## 3. Codex View

Status: `in progress`

The Codex View is an entity-oriented projection over VaERL.

It is not a separate database and not a parallel canon source.

### 3.1 Characters

Character notes should expose:

- canonical name
- preferred slug
- aliases
- summary
- key facts
- relationships
- relationship facts
- chapters where the character appears
- review/canonical state
- evidence
- tags
- confidence
- source mentions
- unresolved or suspicious aliases

### 3.2 Places

Places include:

- physical places
- countries
- kingdoms
- cities
- regions
- minor settings
- politically relevant territories
- relationship to characters and events

### 3.3 Factions

Factions include:

- organizations
- kingdoms when they act as political agents
- noble houses
- councils
- armies
- institutions
- religious or magical orders

### 3.4 Objects

Objects include:

- narratively relevant objects
- magical artifacts
- weapons
- symbols
- relics
- personal items with relationship or continuity weight

### 3.5 Concepts

Concepts include:

- magic systems
- world rules
- cultural concepts
- phenomena
- proprietary terms
- metaphysical or political mechanisms

### 3.6 Events

Not every event should become a primary entity.

Event levels:

- Minor chapter event: usually a fact, relationship fact, or chapter summary item.
- Structural story event: may deserve a primary event entity.
- Historical/worldbuilding event: may deserve a primary event entity.

Example:

- "Sera escaped the castle" can live as a fact or relationship if it does not need a note.
- "The war between two countries" can be a primary event if it structures history, politics, or future continuity.

## 4. Story Bible View

Status: `not started`

The Story Bible View is a human editorial layer generated from VaERL.

It should be more readable and less mechanical than the Codex View.

Possible sections:

- work overview
- main cast
- secondary cast
- world overview
- political structure
- magic / power systems
- timeline
- factions
- locations
- important objects
- open questions
- continuity risks
- relationship map
- unresolved mysteries
- plot threads
- themes and motifs

The Story Bible must not be a JSON dump. It should be produced from VaERL and then passed through editorial synthesis.

## 5. Editorial Synthesis Layer

Status: `not started`

Objective:

> Convert structured VaERL into useful human editorial output.

Some views should be generated in two steps.

### 5.1 Step 1 — Retrieval From VaERL

Retrieve:

- relevant entities
- relationships
- facts
- chapters
- evidence
- review states
- conflicts
- uncertainties
- source references

### 5.2 Step 2 — Editorial Writing With LLM

The LLM does not invent canon. The LLM writes human-useful prose from VaERL.

It may produce:

- editorial character sheet
- character arc summary
- world sheet
- faction summary
- readable timeline
- inconsistency report
- Story Bible section
- notes for author/editor

Critical rule:

> The LLM is not the source of truth here. VaERL is.

The LLM may:

- synthesize
- order
- explain
- rewrite for readability
- flag uncertainty
- propose review actions

The LLM must not:

- invent facts
- resolve conflicts silently
- promote entities
- modify canon without explicit action
- hide review state

## 6. Review Queue

Status: `in progress`

The Review Queue is a working view over uncertainty.

TextifAI should not pretend to have perfect certainty. A good Review Queue is a product strength, not a failure.

It should support review of:

- entities in review
- doubtful aliases
- suggested merges
- duplicate entities
- unresolved mentions
- weak relationships
- type conflicts
- low-confidence entities
- language inconsistencies
- linking issues
- canon conflicts
- possible over-merge
- possible missing merge

Future actions:

- accept primary
- merge into primary
- reject alias
- promote entity
- demote entity
- edit canonical name
- mark as duplicate
- mark as false positive
- regenerate editorial synthesis
- lock canonical decision
- attach evidence
- split contaminated entity

### 6.1 Canonical Write-Back

Some user actions change VaERL. Some only change presentation.

Canonical write-back actions:

- merge review entity into primary
- merge primary into primary
- reject alias
- accept alias
- rename canonical entity
- change preferred slug
- change entity kind or subkind
- promote entity
- demote entity
- mark fact as false
- add confirmed fact
- lock canonical decision

Presentation/editorial-only actions:

- rewrite summary
- reorder facts
- change section layout
- regenerate Story Bible prose
- hide/show tags in a view

Rules:

- Canon changes must be explicit.
- Canon changes must be auditable.
- Human corrections should feed back into VaERL.
- The system must not silently rewrite canon because a generated note sounds better.
- Review history should make it possible to understand why a decision was made.

## 7. Editor / Manuscript View

Status: `not started`

The editor is a Markdown manuscript interface backed by VaERL.

It should include:

- online Markdown editor
- chapter navigation
- side panel of detected entities
- links to Codex View
- mention highlights
- inconsistency warnings
- continuity suggestions
- quick review actions
- chapter ↔ entity relationships
- paragraph ↔ evidence spans in the future

Core rule:

> The editor does not replace VaERL. The editor consumes and updates VaERL.

Possible future features:

- inline entity mentions
- quick merge
- regenerate chapter summary
- detect new entity
- compare chapter against canon
- continuity warnings
- contradiction detection
- rewrite assistance grounded in VaERL
- style-aware but canon-safe rewrite suggestions

## 8. Query Layer

Status: `not started`

The Query Layer is critical.

TextifAI should not answer author questions through flat RAG over Markdown.

Target flow:

```text
author query -> query understanding -> retrieval plan -> VaERL retrieval -> evidence assembly -> LLM answer
```

The LLM should not answer directly against raw novel text. It should answer using enriched context assembled from VaERL.

### 8.1 Query Understanding

Query Understanding converts the author's question into structure.

Example:

```json
{
  "intent": "character_knowledge_before_event",
  "entities": ["Sera", "Nerys"],
  "event_constraint": "huida del castillo",
  "time_scope": "before",
  "needs_evidence": true
}
```

It should detect:

- mentioned entities
- intent type
- temporal scope
- chapter scope
- need for textual evidence
- whether the question is about canon, style, continuity, editing, or brainstorming
- whether review-state data should be included

### 8.2 Retrieval Planning

Retrieval Planning decides what to retrieve:

- only entity
- entity + relationships
- chapters
- chapter summaries
- evidence spans
- timeline
- review notes
- unresolved mentions
- relationship subgraph
- source excerpts

It should not put the whole novel into context.

### 8.3 Graph Retrieval

Graph Retrieval should retrieve:

- primary entities
- review entities when relevant
- aliases
- relationships
- chapter refs
- confidence
- review state
- tags
- subkinds
- source mentions

### 8.4 Evidence Retrieval

Evidence Retrieval should retrieve textual or semi-structured support:

- chapter summaries
- fragments
- evidence spans
- nearby mentions
- source excerpts
- scene-level context if available

If evidence spans do not exist yet, this roadmap treats them as a future required artifact.

### 8.5 Context Assembly

Context Assembly builds an answer package separating:

- confirmed facts
- inference
- relationships
- evidence
- uncertainty
- review data
- missing data
- contradictory or conflicting data

### 8.6 Answer Generation

The final answer should:

- use VaERL as source
- cite or reference chapters when useful
- distinguish fact from inference
- warn when something is in review
- avoid invented canon
- answer in the author's working language
- expose uncertainty instead of hiding it

## 9. Query Layer Modes

Status: `not started`

### 9.1 Fixed Commands / Guided Workflows

Examples:

- `/review`
- `/proofread`
- `/brainstorm`
- `/continuity-check`
- `/summarize-character`
- `/find-contradictions`
- `/expand-scene`
- `/compare-with-canon`
- `/extract-new-entities`
- `/merge-suggestions`
- `/what-does-character-know`

Each command should define:

- expected input
- retrieval strategy
- VaERL context needed
- output format
- whether it can modify VaERL or only suggest changes
- audit behavior

### 9.2 Free Author Chat

In free chat, the author can talk naturally.

Even in free chat:

> Every answer must be VaERL-enriched before reaching the LLM.

Flow:

```text
free user message -> query understanding -> VaERL retrieval -> context assembly -> LLM answer
```

Example questions:

- "Que sabe Sera sobre Nerys antes de huir?"
- "Donde he insinuado ya lo del Baculo?"
- "Ren esta contradiciendose aqui?"
- "Que personajes tienen relacion con Veredyn?"
- "Dame ideas para continuar esta escena sin romper el canon."
- "Revisa este capitulo contra el VaERL."

## 10. Difference From Codex / Story Bible Products

Status: `in progress`

TextifAI is not "a Codex with chat".

Layer separation:

- VaERL is the semantic source of truth.
- Codex View is an entity view.
- Story Bible View is an editorial view.
- Review Queue is a correction workflow.
- Query Layer is the reasoning and retrieval interface.
- Editor View is the writing interface.

Product framing:

> TextifAI is a semantic story engine with multiple views.

This matters because the same semantic model should support:

- author browsing
- continuity checks
- future chat
- manuscript editing
- review actions
- Story Bible exports
- Obsidian vaults
- future web views

## 11. Roadmap By Phase

### Phase 1 — Stabilize VaERL Core

Status: `in progress`

Objective:

Stabilize the semantic base: entity identity, replay, canonical naming, slugs, review states, language consistency, and reliable import artifacts.

Why it matters:

Every later product surface depends on VaERL quality. If VaERL is unstable, chat and editor features will amplify errors.

Prerequisites:

- frozen upstream artifacts
- downstream replay
- current `obsidian_import.json`
- vault materialization
- semantic diagnosis playbook

Outputs:

- stable VaERL artifacts
- clean primary/review split
- reliable Markdown vault
- run comparability manifest
- semantic invariant suite (`semantic_invariants_audit.json`)
- replayable entity resolution and cleanup

Risks:

- overfitting to one novel
- hidden LLM variance
- noisy auxiliary enrichment
- review queue becoming too large
- protagonist identity instability

Blockers:

- semantic invariant suite exists, but current gates still expose unresolved VaERL issues
- lack of evidence spans
- incomplete author correction loop

Done criteria:

- 20/20 and larger runs keep stable protagonist primaries
- no broken wikilinks/placeholders
- no language contamination in semantic prose
- review queue is useful and explainable
- downstream replay can validate changes cheaply
- auxiliary docs can enrich without destabilizing core primaries

Signals mature enough to move on:

- manual vault review finds mostly editorial issues, not structural bugs
- comparable replay runs show stable primary counts and identities
- major merge/review decisions are auditable
- authors can inspect the vault and understand the graph

### Phase 2 — Codex View

Status: `in progress`

Objective:

Turn VaERL entities into a polished, browsable Codex surface.

Why it matters:

Authors need a reliable way to inspect what TextifAI thinks the story contains.

Prerequisites:

- stable primaries
- stable slugs
- useful tags
- review state preserved
- readable primary note summaries

Outputs:

- polished primary notes
- entity browser
- filters by kind/tag/review state
- merge/review actions
- relation display
- source/evidence display when available

Risks:

- Codex becoming a parallel source of truth
- over-polished prose hiding uncertainty
- UI encouraging unsafe merges

Blockers:

- no interactive review write-back yet
- evidence spans not available

Done criteria:

- author can browse major entities comfortably
- review entities are discoverable but not overwhelming
- actions clearly distinguish presentation edits from canon changes

Signals mature enough to move on:

- Codex is useful without opening raw JSON
- author can correct obvious entity issues
- canonical write-back rules are clear

### Phase 3 — Story Bible View

Status: `not started`

Objective:

Generate human-readable editorial story bible sections from VaERL.

Why it matters:

Authors need a coherent editorial overview, not just entity cards.

Prerequisites:

- Codex View quality
- editorial synthesis layer
- source/evidence availability
- review-state-aware output

Outputs:

- generated story bible sections
- main cast overview
- world overview
- magic/political systems
- timeline draft
- open questions
- continuity risks
- exportable Story Bible

Risks:

- LLM smoothing over canon uncertainty
- generated prose inventing connective tissue
- stale Story Bible after VaERL corrections

Blockers:

- no synthesis audit yet
- no regeneration strategy after corrections

Done criteria:

- Story Bible sections cite or trace back to VaERL
- uncertain material remains visible
- generated sections are useful to an author without being treated as hidden canon

Signals mature enough to move on:

- Story Bible helps manual review
- author can regenerate sections safely
- no major canon drift from synthesis

### Phase 4 — Query Layer v1

Status: `not started`

Objective:

Build structured querying over VaERL with fixed commands and controlled retrieval.

Why it matters:

This is the bridge from static vault to interactive assistant.

Prerequisites:

- stable VaERL
- usable Codex View
- basic evidence retrieval or chapter summary fallback
- query understanding schema

Outputs:

- query understanding
- retrieval planner
- graph retrieval
- context assembly
- fixed command layer
- grounded answer generation

Risks:

- flat RAG temptation
- LLM answering beyond VaERL
- weak temporal reasoning
- poor handling of review-state data

Blockers:

- evidence spans not implemented
- timeline model not mature

Done criteria:

- fixed commands answer with VaERL-grounded context
- missing evidence is reported clearly
- answers distinguish fact, inference, and review state

Signals mature enough to move on:

- authors can ask common bounded questions reliably
- answers are useful without loading whole manuscript
- hallucinated canon is rare and detectable

### Phase 5 — Free Author Chat

Status: `not started`

Objective:

Support natural author conversation grounded in VaERL.

Why it matters:

This is where TextifAI becomes a practical writing partner instead of only a compiler/browser.

Prerequisites:

- Query Layer v1
- robust intent detection
- review-state-aware answer policy
- context assembly quality

Outputs:

- VaERL-enriched free chat
- uncertainty-aware answers
- chapter-aware responses
- evidence-grounded replies
- brainstorming mode that respects canon

Risks:

- chat bypassing VaERL
- user mistaking suggestions for canon
- poor separation between brainstorming and confirmed story facts

Blockers:

- no author correction loop
- no durable conversation-to-canon policy

Done criteria:

- chat answers are consistently grounded
- brainstorming suggestions do not silently modify canon
- author can request evidence or review state

Signals mature enough to move on:

- free chat improves writing decisions without corrupting VaERL
- common author questions work better than generic AI chat

### Phase 6 — Online Markdown Editor

Status: `not started`

Objective:

Provide a manuscript writing interface integrated with VaERL.

Why it matters:

The author should be able to write where TextifAI can detect mentions, continuity risks, and review opportunities.

Prerequisites:

- Codex View
- Query Layer
- canonical write-back
- stable Markdown/vault sync policy

Outputs:

- online Markdown editor
- chapter panel
- entity side panel
- inline highlights
- quick review actions
- continuity warnings
- rewrite assistance grounded in VaERL

Risks:

- editor complexity overwhelming semantic core
- sync conflicts with Obsidian or filesystem
- suggestions becoming too intrusive

Blockers:

- no final storage/sync strategy
- no evidence span anchoring

Done criteria:

- author can write/edit chapters
- detected mentions link to VaERL
- warnings are useful and not noisy
- quick corrections feed back into VaERL

Signals mature enough to move on:

- editor increases author productivity without becoming a separate canon surface

### Phase 7 — Advanced Semantic Engine

Status: `not started`

Objective:

Add deeper semantic reasoning once the core product loop is stable.

Why it matters:

This is where TextifAI can surpass simple Codex/story-bible tools.

Prerequisites:

- stable VaERL
- evidence spans
- reliable query layer
- author correction loop
- timeline/event representation

Outputs:

- evidence spans
- timeline graph
- contradiction detection
- character knowledge modeling
- point-of-view consistency
- rewrite assistant grounded in VaERL
- scene-level semantic checks
- advanced relationship evolution

Risks:

- over-modeling before core workflows are useful
- false positives in contradiction detection
- treating uncertain inferred timelines as canon

Blockers:

- no mature evidence model
- no timeline confidence model
- insufficient author feedback data

Done criteria:

- advanced checks catch real issues with low noise
- character-knowledge queries become reliable
- rewrite assistance preserves canon and voice constraints

Signals mature enough to move on:

- advanced features improve real author workflow beyond what manual Codex browsing can do

## 12. Phase Status Tracker

| Phase | Status | Current Focus | Move-Next Signal |
| --- | --- | --- | --- |
| Phase 1 — Stabilize VaERL Core | `in progress` | replay, invariants, auxiliary docs, primary quality | stable larger runs and useful review queue |
| Phase 2 — Codex View | `in progress` | readable primary notes and inspectable vault | author can correct obvious entity issues |
| Phase 3 — Story Bible View | `not started` | not active | Codex and synthesis layer stable |
| Phase 4 — Query Layer v1 | `not started` | not active | fixed retrieval packages from VaERL |
| Phase 5 — Free Author Chat | `not started` | not active | fixed commands work reliably |
| Phase 6 — Online Markdown Editor | `not started` | not active | query/review write-back stable |
| Phase 7 — Advanced Semantic Engine | `not started` | not active | evidence spans and timeline model exist |

## 13. TODO List

### 13.1 Immediate TODO

- Expand semantic invariant suite from current Phase 1 gates.
- Validate downstream replay against frozen good upstream.
- Keep improving stable canonical naming.
- Continue primary note synthesis quality work.
- Clean up Review Queue noise.
- Define evidence span plan.
- Validate auxiliary docs with hints as recommended product path.
- Decide minimum acceptable VaERL quality gate for moving into Query Layer v1.

### 13.2 Medium-Term TODO

- Codex View MVP.
- Review action MVP: merge review into primary, reject alias, promote/demote.
- Story Bible generator.
- Editorial synthesis layer.
- Query planner MVP.
- Fixed command layer.
- Context assembly format.
- Evidence retrieval fallback using chapter summaries.

### 13.3 Long-Term TODO

- Free author chat.
- Online Markdown editor.
- Timeline reasoning.
- Contradiction detection.
- Character knowledge modeling.
- Advanced VaERL graph.
- Scene-level evidence spans.
- Rewrite assistant grounded in VaERL.

## 14. Important Design Principles

- VaERL is source of truth.
- Views are projections over VaERL.
- LLMs synthesize; they do not own canon.
- Every generated answer should be grounded.
- Review state matters.
- Uncertainty must be visible.
- Replayability matters.
- Markdown is a first-class output.
- Author corrections should feed back into VaERL.
- No hidden canon changes.
- Hints from the author should be encouraged when ingesting auxiliary documents.
- Missing hints should not make clear auxiliary facts unusable.
- Frozen artifacts should be used whenever possible to reduce cost and variance.

## 15. Out Of Scope For This Document

This roadmap does not define:

- detailed prompts
- final UI wireframes
- pricing
- deployment architecture
- final choice of web-only vs Obsidian-only vs hybrid surfaces
- exact database schema
- low-level pipeline contracts
- provider/model selection policy
- full test plans
- all command syntaxes

Those belong in implementation docs, product specs, or task-specific design notes.
