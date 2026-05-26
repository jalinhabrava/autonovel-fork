# TextifAI Open Design + Codex MCP Setup (Dev-only)

## Scope
Open Design se usa como herramienta externa de diseño para iterar Dashboard/Graph/Wiki/Node Detail/Editor shell. No es dependencia runtime de TextifAI.

## Install Path
`/tmp/textifai_dev_tools/open-design`

## Commands Used
```bash
mkdir -p /tmp/textifai_dev_tools
cd /tmp/textifai_dev_tools
git clone https://github.com/nexu-io/open-design.git
cd open-design
corepack enable
corepack pnpm install --frozen-lockfile
corepack pnpm --filter @open-design/daemon build
```

## Runtime Note
Open Design exige Node `~24`. En este entorno hay Node `v22.22.2`. Resultado:
- dependencias: instaladas;
- daemon/web runtime: bloqueado hasta cambiar a Node 24.

## Start/Stop (cuando Node 24 esté activo)
```bash
cd /tmp/textifai_dev_tools/open-design
nvm use 24
corepack pnpm install --frozen-lockfile
corepack pnpm tools-dev start web --daemon-port 7457 --web-port 5175
corepack pnpm tools-dev status
corepack pnpm tools-dev stop
```

## MCP / Codex Snippet (manual)
```json
{
  "mcpServers": {
    "open-design": {
      "command": "node",
      "args": [
        "/tmp/textifai_dev_tools/open-design/apps/daemon/dist/cli.js",
        "mcp",
        "--daemon-url",
        "http://127.0.0.1:7457"
      ]
    }
  }
}
```

## How to Use for TextifAI
1. Seleccionar skills: `design-review`, `plan-design-review`, `web-design-guidelines`, `d3-visualization`.
2. Seleccionar design systems base: `dashboard`, `notion`, `linear-app`, `minimal`.
3. Ejecutar review sobre superficies: Dashboard, Graph, Wiki, Node Detail, Editor shell.
4. Exportar recomendaciones y aplicar top 3 cambios por iteración.

## Rollback
```bash
rm -rf /tmp/textifai_dev_tools/open-design
```

## Safety
- Dev-only.
- No modificar `package.json`/`package-lock.json` de TextifAI.
- No commitear repo Open Design ni outputs privados generados.
