# Safepoint Convention

Safepoints are small, coherent Git checkpoints that make TextifAI work recoverable and reviewable.

## Commit Naming

Safepoint commit subjects use this format:

```text
safepoint-XXX short description
```

Examples:

```text
safepoint-001 operationalization docs
safepoint-002 tighten VaERL invariant audit
safepoint-003 document replay validation flow
```

Use a three-digit monotonically increasing number. Do not reuse safepoint numbers.

## Handoff Naming

Each safepoint commit should include a matching handoff file:

```text
docs/handoffs/safepoint-XXX_handoff.md
```

The `XXX` value must match the commit subject.

## Commit Body

The commit body should include:

- scope
- files changed
- validation
- known risks
- next step

Validation status must be explicit. Do not hide failed validation.

## Scope Discipline

Safepoints should happen after coherent, verified, small changes.

Do not bundle unrelated changes.

Do not include local scratch files, secrets, generated outputs, or preservation-zone changes unless explicitly approved.

If the user has modified files outside scope, preserve them and mention them in the handoff. Do not stage them.

## Review Flow

Before editing:

1. Check `git status --short`.
2. Identify latest safepoint number.
3. Announce planned next safepoint number if a commit is expected.
4. Confirm scope and validation tier.

After editing:

1. Run agreed validation.
2. Check `git status --short`.
3. Check `git diff --stat`.
4. Review changed files for scope.
5. Stage only intentional files.
6. Create safepoint commit only after approval when approval is required.
