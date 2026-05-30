# SP-114 ProjectStore / SQLite / .txtfai Architecture ADR

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and document stable hybrid project data architecture for TextifAI before full write-back migration.

**Architecture:** Keep Markdown as author-facing substrate, add per-project SQLite for operational data, retain JSON as snapshot/debug/export format. Add lightweight schema stub and architecture tests to lock contracts.

**Tech Stack:** Python docs/tests, SQLite SQL schema draft, unittest, Git.

---

### Task 1: Author contract docs
- [x] Create ADR with problem, alternatives, decision, migration/local/SaaS/txtfai/vector sections.
- [x] Create live `.textifai` folder contract.
- [x] Create `.txtfai` bundle contract.

### Task 2: Define data contracts
- [x] Create SQLite schema v0 documentation with required tables.
- [x] Create ProjectStore contract README with minimal API.

### Task 3: Add schema draft artifact
- [x] Create `textifai/project_store/schema.sql` with required v0 tables.

### Task 4: Add contract fixtures
- [x] Create four expected JSON reports under `tests/fixtures/textifai/project_store_architecture/expected/`.

### Task 5: Add architecture tests
- [x] Create `tests/test_textifai_project_store_architecture.py` validating docs/contracts/safety constraints.
