# SP-125A Theme Token Scaffold

## Purpose

SP-125A introduces non-visual theme token scaffolding for TextifAI Arc. Goal is to define semantic theme names without migrating component visuals yet.

## Scope

- Adds CSS custom properties for app surfaces, borders, text, accents, status, and effects.
- Extends Tailwind with semantic `txf` theme names backed by those variables.
- Preserves current component structure in SP-125A/SP-125B.
- Does not migrate TSX components to new tokens yet.
- Does not change graph visual semantics in code.

## Current mapped values

These scaffold tokens are now mapped to product-web palette values or explicitly documented Arc app extensions.

## Token groups

- `--txf-color-bg`
- `--txf-color-bg-elevated`
- `--txf-color-surface`
- `--txf-color-surface-muted`
- `--txf-color-border`
- `--txf-color-border-strong`
- `--txf-color-text`
- `--txf-color-text-muted`
- `--txf-color-text-subtle`
- `--txf-color-accent`
- `--txf-color-accent-hover`
- `--txf-color-accent-soft`
- `--txf-color-danger`
- `--txf-color-danger-soft`
- `--txf-color-success`
- `--txf-color-success-soft`
- `--txf-color-warning`
- `--txf-color-warning-soft`
- `--txf-shadow-card`
- `--txf-radius-card`
- `--txf-radius-button`

## Product website palette source of truth

TextifAI Arc should converge toward product-web palette source of truth at `/home/david/projects/textifai-web`. SP-125A introduces style control. SP-125B maps Arc tokens to product-web palette. SP-125C+ will migrate components.

## SP-125B product-web palette mapping

### Product-web source path

- `/home/david/projects/textifai-web`

### Final Arc token values selected

| Token | Value | Type |
| --- | --- | --- |
| `--txf-color-bg` | `#f7f1e7` | direct product-web |
| `--txf-color-bg-elevated` | `#efe4d6` | direct product-web |
| `--txf-color-surface` | `rgba(255, 251, 245, 0.88)` | direct product-web |
| `--txf-color-surface-muted` | `#fffaf3` | direct product-web |
| `--txf-color-border` | `rgba(124, 97, 72, 0.18)` | direct product-web |
| `--txf-color-border-strong` | `rgba(124, 97, 72, 0.28)` | Arc extension |
| `--txf-color-text` | `#211913` | direct product-web |
| `--txf-color-text-muted` | `#6f6256` | direct product-web |
| `--txf-color-text-subtle` | `rgba(111, 98, 86, 0.72)` | Arc extension |
| `--txf-color-accent` | `#b77a4b` | direct product-web |
| `--txf-color-accent-hover` | `#9f673d` | Arc extension |
| `--txf-color-accent-soft` | `rgba(183, 122, 75, 0.14)` | direct product-web |
| `--txf-color-danger` | `#b4544f` | Arc extension |
| `--txf-color-danger-soft` | `rgba(180, 84, 79, 0.14)` | Arc extension |
| `--txf-color-success` | `#4f7a5c` | Arc extension |
| `--txf-color-success-soft` | `rgba(79, 122, 92, 0.14)` | Arc extension |
| `--txf-color-warning` | `#a16d3b` | Arc extension |
| `--txf-color-warning-soft` | `rgba(161, 109, 59, 0.14)` | Arc extension |
| `--txf-shadow-card` | `0 18px 60px rgba(49, 33, 19, 0.08)` | direct product-web |
| `--txf-radius-card` | `24px` | direct product-web |
| `--txf-radius-button` | `999px` | direct product-web |

### Arc app extension tokens

- `--txf-color-action: #8f5a2a`
- `--txf-color-action-hover: #6f4321`
- `--txf-color-action-soft: rgba(183, 122, 75, 0.14)`
- `--txf-color-nav-active: #8f5a2a`
- `--txf-color-nav-active-text: #fdf7f0`
- `--txf-color-focus-ring: rgba(183, 122, 75, 0.38)`

These are future-facing app interaction tokens. They do not imply broad SP-125B component migration.

## Graph semantic color separation

Graph visuals stay unchanged in SP-125A/SP-125B. Future graph token group proposal only:

- `--txf-graph-character`
- `--txf-graph-concept`
- `--txf-graph-event`
- `--txf-graph-object`
- `--txf-graph-place`
- `--txf-graph-review`
- `--txf-graph-unresolved`
- `--txf-graph-link`
- `--txf-graph-link-active`

## Migration plan

- SP-125A: scaffold tokens only.
- SP-125B: map tokens to product-web palette source.
- SP-125C+: migrate one low-risk shell/component layer at a time.

## Explicit non-goals

- No broad component class replacement.
- No visual redesign by ad hoc scattered overrides.
- No graph color change.
- No manual edit to generated `textifai/web_viewer/static/react-shell/app.css`. This file may change only as build output from `textifai_react_build.sh`.
