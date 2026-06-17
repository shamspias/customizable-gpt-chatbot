# Screenshots

Product screenshots used by the top-level `README.md`. Captured at 1440×900 (2×).

| File | View |
|---|---|
| `home.png` | Home dashboard — smart composer, KPI strip, agent board, recent activity |
| `agents.png` | All agents — the gallery with tag filters, Chat / Builder per agent |
| `plugins.png` | Plugins & connectors — installed MCP connectors + the template gallery |
| `setup.png` | First-run install wizard — name the workspace, check providers, create the admin |
| `signin.png` | Sign-in gate |
| `knowledge.png` | Knowledge bases — KBs + retrieval config + documents |
| `activity.png` | Activity — the durable run log |
| `insights.png` | Insights — usage / cost / reliability rollups |

## Recapture

```bash
cd apps/web && npm run dev          # serves the SPA on :5173
```

Either point a browser at a real backend (`make up`), or use the **dev-only demo
data** (no backend needed):

- `http://localhost:5173/?demo` — Home, populated
- `http://localhost:5173/?demo=plugins` — any shell view (`workflows`, `knowledge`, …)
- `http://localhost:5173/?demo=setup` — the install wizard

`?demo` stubs the API with fixtures and is **dev-only** — it is dead-stripped from
production builds (`npm run build`).
