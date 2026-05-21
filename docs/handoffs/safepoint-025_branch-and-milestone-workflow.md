# Branch & Milestone Workflow

## Scope

Phase 1.3.C2 organizó política Git/ramas/hitos antes de continuar con núcleo ingestion/VaERL.

Incluido:

- verificación de `safepoint-024`
- reconocimiento seguro de branch actual y upstream
- reconocimiento seguro de untracked persistentes locales
- documento nuevo de política de ramas e hitos
- decisión de rama activa recomendada para Phase 1.3

Excluido:

- sin cambios de runtime
- sin cambios de pipeline
- sin cambios en `textifai/**`, `scripts/**`, `tests/**`
- sin merge a `main`
- sin cambios en `.gitignore`

## Files Changed

- `docs/operations/branch-and-milestone-workflow.md`
- `docs/handoffs/safepoint-025_branch-and-milestone-workflow.md`

## Branch Policy

Política definida:

- `main` = rama estable/usable
- phase branches = trabajo activo por hito
- hotfix branches = correcciones urgentes y acotadas
- safepoints siempre pequeños, versionados y pusheados en rama activa
- merge a `main` solo al cerrar hito y tras validación
- tags de milestone opcionales al cierre

## Active Branch Decision

Decisión actual:

- usar rama `phase-1.3-ingestion-vaerl-hardening`
- crearla desde `HEAD` actual si estábamos en `main`
- publicar rama con upstream

## Untracked Local Files Policy

Estado observado:

- `.codegraph/` no ignorado actualmente; tratado como tooling local
- `.superpowers/` no ignorado actualmente; tratado como tooling local
- `package.json` root no ignorado; decisión pendiente
- `package-lock.json` root no ignorado; decisión pendiente

Política propuesta:

- no borrar estos archivos
- no stagearlos en safepoints normales
- no tocar `.gitignore` todavía
- revisar `package.json`/`package-lock.json` root en una fase separada si se quiere decidir ignorarlos o versionarlos

## Commands Run

- `git status --short`
- `git log --oneline -n 8`
- `git rev-parse --short HEAD`
- `git status -sb`
- `git check-ignore -v .codegraph .superpowers package.json package-lock.json || true`
- reconocimiento seguro de inventario local con `find`/`stat`
- lectura de:
  - `docs/operations/safepoint-convention.md`
  - `docs/operations/repo-zones.md`

## Validation Performed

- `git status --short`
- `git branch --show-current`
- `git log --oneline -n 8`
- `git diff --stat`

## Semantic Contract Changes: NO

## Runtime Changes: NO

## Write-back: NO

## Generated Artifacts: NO

## Next Suggested Phase

Phase 1.3.D — Replay Baseline Harness.
