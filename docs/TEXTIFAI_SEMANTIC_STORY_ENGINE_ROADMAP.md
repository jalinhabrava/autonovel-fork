# TextifAI Narrative Semantic Engine Roadmap

Status: living roadmap

Last updated: 2026-05-20

## How To Use This Document

This document is a technical and operational roadmap for TextifAI.

Use it to:

- align architecture decisions with product identity
- define safe implementation phases
- separate semantic contracts from generation behavior
- decide validation depth by semantic risk
- track maturity gates before enabling higher-level workflows

This is not a marketing page. This is not a closed implementation spec.

Related operational docs:

- `docs/ARCHITECTURE.md`
- `docs/BOOTSTRAP_V1_FLOW.md`
- `docs/VAULT_SCHEMA.md`
- `docs/e2e_semantic_diagnosis_rules.md`
- `docs/operations/semantic-contracts.md`
- `docs/operations/validation-surface-inventory.md`
- `docs/operations/safe-fixtures-and-baselines.md`

---

## 1) Product Identity

TextifAI is:

- a **Narrative Semantic Engine**
- and a **Narrative Harness**

TextifAI is not:

- just RAG
- just entity extraction
- just a Story Bible generator
- just an AI editor
- just a Codex for fiction
- just prompt engineering

TextifAI transforms long-form narrative material into:

- durable semantic memory
- structured narrative state
- grounded retrieval context
- continuity-aware writing context
- inspectable canon memory
- reusable editorial infrastructure

**Core statement**

> TextifAI does the semantic and contextual heavy lifting required for long-form narrative continuity.

---

## 2) System Framing

TextifAI is a layered system where canon memory, retrieval, and generation are deliberately separated.

### 2.1 Narrative Semantic Engine

Responsible for:

- ingestion and normalization
- semantic extraction and reconciliation
- canonical memory stabilization
- invariant enforcement
- review-state visibility
- replayable semantic compilation

### 2.2 Narrative Harness

Responsible for:

- author-intent interpretation
- retrieval planning
- narrative-state retrieval
- evidence assembly
- continuity-safe context packaging
- generation-time constraint delivery

### 2.3 Generation Layer

Responsible for:

- synthesis, continuation, rewriting, brainstorming, editorial drafting
- only over harness-provided context
- no silent canon mutation

### 2.4 Observability + Editorial Layer

Responsible for:

- semantic debugging
- continuity inspection
- review queue execution
- author corrections and explicit write-back

---

## 3) Narrative Harness

The Narrative Harness is the control plane between author intent and LLM generation.

It must:

- transform author intent into grounded narrative context packages
- assemble continuity-safe context before generation reaches the LLM
- retrieve semantic state instead of dumping raw manuscript chunks
- separate canon from generation
- prevent silent canon drift

Harness context package should include:

- canon facts
- narrative state
- character knowledge boundaries
- relationship state
- unresolved tensions
- stylistic constraints
- POV constraints
- timeline constraints
- evidence
- uncertainty
- review state

**Responsibility statement**

> The LLM should not be responsible for remembering the novel.
> TextifAI should be responsible for constructing the correct narrative context.

---

## 4) Narrative State

Long-form continuity needs state transitions, not only entity recall.

TextifAI should model:

- entities
- relationships
- facts

and also:

- what changed
- who learned what
- emotional evolution
- promises
- secrets
- authority shifts
- symbolic recurrences
- unresolved tensions
- narrative role transitions
- continuity-sensitive states

Narrative-state tracking must be explicit enough to audit why a generated segment was allowed, constrained, or flagged.

---

## 5) VaERL Reframe

Status: `in progress`

VaERL is:

- semantic memory
- canonical narrative memory
- auditable semantic state
- retrieval substrate
- grounding layer

VaERL is not:

- a Markdown folder
- a prompt dump
- a vector DB replacement
- a transient generation cache

VaERL remains central for:

- semantic invariants
- replayability
- auditability
- visible review state
- explicit canon write-back

### 5.1 VaERL Invariants (preserved)

Core invariants:

- VaERL is source of truth for canon memory.
- No hidden canon changes.
- Views are projections over VaERL, not independent canon stores.
- Canonical naming and slug policy remain stable and explicit.
- Facts, uncertainty, inference, and author corrections stay distinguishable.
- Merge and resolution decisions remain auditable.
- Replayability and comparability remain first-class.

### 5.2 VaERL Maturity Signals (refined)

Maturity indicators:

- stable primary entities across comparable runs
- stable slug and naming policies
- useful review queue (signal > noise)
- strong invariant pass rates on fixture and approved corpora
- reproducible downstream replay behavior
- inspectable evidence linking between state and outputs

---

## 6) Query + Retrieval Reframe

Status: `not started` as full layer, `partially active` in tactical flows.

The query path is reframed as:

**author intent**
→ **query understanding**
→ **retrieval planning**
→ **narrative state retrieval**
→ **evidence retrieval**
→ **context assembly**
→ **grounded generation**

Priority shifts away from “chatting with the novel” toward controlled retrieval and synthesis.

### 6.1 Query Understanding

Should classify:

- continuity check
- rewrite request
- what-if exploration
- canon lookup
- relation/timeline clarification
- unresolved review follow-up

### 6.2 Retrieval Planning

Should choose retrieval mix:

- semantic graph lookup
- narrative state snapshot
- evidence spans
- review-state signals
- policy constraints (POV, timeline, style)

### 6.3 Context Assembly

Should build deterministic context envelopes with:

- cited canon assertions
- uncertainty markers
- open review items
- reasoned inclusion/exclusion boundaries

---

## 7) Generation Philosophy

LLMs may:

- synthesize
- continue
- rewrite
- brainstorm
- editorialize

LLMs must not:

- silently mutate canon
- become source of truth
- invent hidden continuity changes
- overwrite semantic memory implicitly

Generation outputs must remain:

- grounded
- inspectable
- evidence-aware
- continuity-aware
- reviewable

Canon updates must happen via explicit write-back workflows, never by implicit side effect.

---

## 8) Viewer + Editor Reframe

### 8.1 Viewer

Status: `in progress`

Viewer is:

- semantic debugger
- narrative observability layer
- continuity inspection surface

Viewer is not merely:

- a graph viewer
- a markdown browser

Minimum viewer value:

- inspect run artifacts quickly
- inspect VaERL/review queue state
- inspect evidence chains and unresolved items
- compare runs and replay effects safely

### 8.2 Future Editor

Status: `not started`

Future editor should be framed as:

- narrative IDE
- continuity-aware manuscript workspace

Editor should consume harness outputs and write corrections back through explicit semantic workflows.

---

## 9) Product Surfaces (Preserved, Reframed)

### 9.1 Codex View

Status: `in progress`

Entity-first projection over VaERL with evidence, relations, review state, and chapter/state links.

### 9.2 Story Bible Layer

Status: `not started`

Synthesis layer over VaERL, not independent canon memory.

### 9.3 Review Queue

Status: `in progress`

Operational surface for unresolved entities, ambiguous merges, weak evidence, relation gaps, and policy violations.

### 9.4 Fixed Workflows

Status: `partially active`

Guided commands for continuity checks, summaries, rewrites, and review resolution under explicit retrieval plans.

### 9.5 Free-Form Author Interaction

Status: `not started`

Allowed only after harness reliability and continuity safety are proven.

---

## 10) Operational Contracts

### 10.1 Semantic Contracts

Any change affecting output shape, canonical naming, slugs, review-state semantics, replay contracts, or note layout is a semantic contract change.

These changes require:

- explicit approval
- explicit validation plan
- fixture/baseline diff strategy
- handoff impact statement

### 10.2 Replayability + Comparability

Replay remains mandatory for:

- validating semantic stability
- checking regressions
- auditing changes across iterations

### 10.3 Canonical Write-Back

Canon change path must remain explicit:

- issue detected
- review decision made
- write-back performed
- evidence and provenance preserved

---

## 11) Roadmap By Phase

### Tactical Pause — Ingestion Observability

Status: `in progress`

Focus:

- local run/vault inspection surfaces
- faster artifact diagnosis
- operational debugging ergonomics

Move-next signal:

- diagnosing ingestion and replay issues is faster than manual folder forensics.

### Phase 1 — Semantic Stabilization

Status: `in progress`

Focus:

- VaERL core stability
- invariants + thresholds
- review-queue signal quality
- replay reliability
- auxiliary ingestion consistency

Move-next signal:

- stable primaries/relations on approved corpus and fixture baselines.

### Phase 2 — Narrative Inspection Surfaces

Status: `in progress`

Focus:

- Codex View usefulness
- reviewer clarity
- evidence inspectability
- author correction readiness

Move-next signal:

- author/reviewer can resolve obvious semantic issues without raw JSON spelunking.

### Phase 3 — Grounded Retrieval Layer

Status: `not started`

Focus:

- intent understanding
- retrieval planning
- narrative-state retrieval
- evidence package assembly

Move-next signal:

- fixed query workflows produce stable, inspectable context packages.

### Phase 4 — Narrative Harness v1

Status: `not started`

Focus:

- continuity-safe context assembly before generation
- policy constraints (POV/timeline/style)
- controlled context package contracts

Move-next signal:

- harness contexts reliably reduce continuity drift in controlled evaluations.

### Phase 5 — Continuity-Aware Generation

Status: `not started`

Focus:

- grounded generation workflows
- evidence-aware drafting
- explicit uncertainty/review feedback loops

Move-next signal:

- generated outputs remain canon-safe under audited harness traces.

### Phase 6 — Narrative IDE Workflows

Status: `not started`

Focus:

- editor workflows for manuscript iteration
- inline continuity diagnostics
- explicit write-back ergonomics

Move-next signal:

- editor actions can update canon safely with traceability.

### Phase 7 — Advanced Narrative State Engine

Status: `not started`

Focus:

- deeper state transitions (knowledge, emotion, authority, promises, secrets)
- richer temporal/event constraints
- symbolic recurrence tracking

Move-next signal:

- state-aware retrieval materially improves continuity over entity-only retrieval.

---

## 12) Phase Status Tracker

| Phase | Status | Current Focus | Move-Next Signal |
| --- | --- | --- | --- |
| Tactical Pause — Ingestion Observability | `in progress` | run/vault inspection speed | debug loops faster than manual forensics |
| Phase 1 — Semantic Stabilization | `in progress` | invariants, replay, review quality | stable semantic outputs on approved baselines |
| Phase 2 — Narrative Inspection Surfaces | `in progress` | codex/review clarity | author can correct canon issues safely |
| Phase 3 — Grounded Retrieval Layer | `not started` | intent + retrieval planning | stable context package generation |
| Phase 4 — Narrative Harness v1 | `not started` | continuity-safe assembly | measurable drift reduction |
| Phase 5 — Continuity-Aware Generation | `not started` | grounded drafting | canon-safe generated workflows |
| Phase 6 — Narrative IDE Workflows | `not started` | editor interactions | safe write-back in author workspace |
| Phase 7 — Advanced Narrative State Engine | `not started` | deep transition modeling | state-aware continuity gains validated |

---

## 13) TODO Structure

### 13.1 Immediate TODO

- Finalize fixture-driven semantic validation baseline (`Phase 0.5` operational track).
- Tighten invariant thresholds without overfitting one novel.
- Standardize handoff reporting for semantic-risk iterations.
- Keep review queue severity and evidence fields actionable.

### 13.2 Medium-Term TODO

- Implement first deterministic context-package contracts for fixed workflows.
- Add narrative-state fields beyond entity/relationship memory.
- Add structured artifact diff tooling for harness outputs.
- Define explicit failure taxonomy for continuity drift.

### 13.3 Long-Term TODO

- Expand temporal/state transition modeling.
- Add stronger author correction feedback loops.
- Mature narrative IDE flows with explicit semantic write-back controls.

---

## 14) Design Principles

- Memory is explicit, not implicit in model context.
- Retrieval is planned, not ad hoc chunk dumping.
- Generation is grounded, not canon-authoritative.
- State transitions matter as much as entity recall.
- Reviewability and auditability are non-negotiable.
- Replayability is mandatory for semantic trust.
- Operational observability is part of product, not auxiliary tooling.

---

## 15) Out Of Scope For This Document

This roadmap does not define:

- low-level function-by-function implementation
- one-off prompt text details
- private novel content
- deployment/commercial packaging strategy
- UI visual design specifications

Those live in implementation plans, tactical handoffs, and module-level docs.
