# SP-125A Theme Token Scaffold

## Purpose

SP-125A introduced semantic theme tokens for TextifAI Arc. SP-125D moves shell and shared surfaces onto approved branded palette board while keeping graph semantics untouched.

## Scope

- Keeps semantic CSS custom properties and Tailwind `txf` names.
- Re-maps Arc shell tokens to approved brand-board palette.
- Applies layered surface rules only in shared shell and shared UI.
- Does not change graph semantic colors in code.
- Does not redesign deep feature modules.

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
- `--txf-color-action`
- `--txf-color-action-hover`
- `--txf-color-action-soft`
- `--txf-color-nav-active`
- `--txf-color-nav-active-text`
- `--txf-color-focus-ring`
- `--txf-color-danger`
- `--txf-color-danger-soft`
- `--txf-color-success`
- `--txf-color-success-soft`
- `--txf-color-warning`
- `--txf-color-warning-soft`
- `--txf-shadow-card`
- `--txf-radius-card`
- `--txf-radius-button`

## SP-125D branded palette mapping

### Approved palette board

- `#F3E9D2` warm parchment
- `#E8D9B8` pale sand
- `#D3B18A` soft copper sand
- `#B5674A` terracotta copper
- `#9C3F2E` deep terracotta
- `#6E5F40` warm brown
- `#3A2A21` dark chocolate

### Final Arc token values selected

| Token | Value | Role |
| --- | --- | --- |
| `--txf-color-bg` | `#f3e9d2` | global page parchment |
| `--txf-color-bg-elevated` | `#e8d9b8` | shell frame / raised base |
| `--txf-color-surface` | `#fbf5e8` | main content cards and topbar |
| `--txf-color-surface-muted` | `#efe1c7` | sidebar, nested bands, muted shared surfaces |
| `--txf-color-border` | `rgba(110, 95, 64, 0.22)` | subtle separators |
| `--txf-color-border-strong` | `rgba(58, 42, 33, 0.28)` | stronger shell separation |
| `--txf-color-text` | `#3a2a21` | primary text |
| `--txf-color-text-muted` | `#6e5f40` | secondary text |
| `--txf-color-text-subtle` | `rgba(110, 95, 64, 0.76)` | tertiary text |
| `--txf-color-accent` | `#b5674a` | warm accent surfaces / hover family |
| `--txf-color-accent-hover` | `#9c3f2e` | stronger accent hover |
| `--txf-color-accent-soft` | `rgba(181, 103, 74, 0.16)` | hover wash |
| `--txf-color-action` | `#9c3f2e` | primary buttons |
| `--txf-color-action-hover` | `#3a2a21` | primary button hover |
| `--txf-color-action-soft` | `rgba(156, 63, 46, 0.14)` | action-adjacent soft fill |
| `--txf-color-nav-active` | `#3a2a21` | active nav fill |
| `--txf-color-nav-active-text` | `#fdf7f0` | active nav / primary action text |
| `--txf-color-focus-ring` | `rgba(181, 103, 74, 0.42)` | focus treatment |
| `--txf-color-danger` | `#9c3f2e` | destructive actions |
| `--txf-color-danger-soft` | `rgba(156, 63, 46, 0.14)` | destructive soft state |
| `--txf-color-success` | `#4f7a5c` | success status |
| `--txf-color-success-soft` | `rgba(79, 122, 92, 0.14)` | success soft state |
| `--txf-color-warning` | `#b5674a` | warning status |
| `--txf-color-warning-soft` | `rgba(181, 103, 74, 0.14)` | warning soft state |
| `--txf-shadow-card` | `0 18px 60px rgba(58, 42, 33, 0.12)` | card shadow |
| `--txf-radius-card` | `24px` | shared card radius |
| `--txf-radius-button` | `999px` | pill/button radius |

### Reserved color usage

- Surfaces stay in parchment, sand, and warm off-white range.
- Actions and active navigation use terracotta to chocolate range.
- Primary text uses dark chocolate; muted text uses warm brown.
- Dark chocolate is reserved for text, active nav, and compact controls, not large backgrounds.

### Layered surface logic

- Page background uses `--txf-color-bg`.
- Outer app frame uses `--txf-color-bg-elevated` so shell separates from page.
- Main content and shared cards use `--txf-color-surface`.
- Sidebar, top bands, chips, and nested shared sections use `--txf-color-surface-muted`.
- Borders escalate from `--txf-color-border` to `--txf-color-border-strong` where stacked shell regions need clearer separation.
- Secondary buttons use bordered `--txf-color-surface` fill so they do not collapse into cards or muted panels.

### Accessibility notes

- Primary text stays on `#3A2A21` for strong contrast over all light surfaces.
- Active nav and primary actions pair dark fill with `#FDF7F0` text.
- Hover fills stay translucent to preserve readable text and visible layering.

## Graph semantic color separation

Graph visuals stay unchanged in SP-125D. No graph node semantic palette changes.

## Migration plan

- SP-125A: scaffold tokens only.
- SP-125B: map tokens to product-web palette source.
- SP-125D: map shell/shared surfaces to approved brand board and enforce layering.
- Future phases: migrate deeper modules one slice at time.

## Future work

- Ingestion progress bars should become realtime state-driven semantic indicators. They should hydrate from ingestion process state and use traffic-light status colors. This is explicitly deferred and not part of SP-129.

## Explicit non-goals

- No graph color change.
- No deep module-specific redesign.
- No manual edit to generated `textifai/web_viewer/static/react-shell/app.css`.
- No manual edit to generated `textifai/web_viewer/static/react-shell/app.js`.
