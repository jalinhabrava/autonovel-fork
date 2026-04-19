# Install TextifAI Obsidian Bridge

## Prerequisites

- Obsidian Desktop
- Node.js / npm

## Build

```bash
cd integrations/obsidian-textifai-bridge
npm install
npm run build
```

Node `18+` is recommended. If the system Node is too old, TextifAI's setup helper attempts a fallback build using `npx -p node@20 -p npm@10`.

## Install into a vault

Create:

- `<vault>/.obsidian/plugins/textifai-bridge/`

Copy into that folder:

- `manifest.json`
- `main.js`

Then in Obsidian:

1. `Settings`
2. `Community plugins`
3. enable `TextifAI Bridge`

## First export

Run:

- `Export TextifAI context snapshot`

This writes by default:

- `<vault>/.textifai/obsidian-bridge-snapshot.json`

## Recommended workflow

- keep auto-export on startup enabled
- keep auto-export on metadata resolution enabled
- let TextifAI prefer the bridge snapshot when it is fresh
