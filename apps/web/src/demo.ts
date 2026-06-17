// Dev-only demo mode: stub the API with representative fixtures so the UI renders a
// populated workspace without a backend — used for design QA and capturing product
// screenshots. Activated only with `?demo` in a dev build (import.meta.env.DEV); the
// dynamic import in main.ts is dead-stripped from production builds.

const now = Date.now();
const ago = (min: number) => new Date(now - min * 60_000).toISOString();

const AGENTS = [
  { id: "a1", name: "Support Concierge", current_version: 3, model: "claude-sonnet-4-6",
    description: "Answers customer questions from the help-center docs, always citing the page.",
    n_tools: 2, n_skills: 1, n_kbs: 1, n_sub_agents: 0, auto_improve: true, tags: ["support"] },
  { id: "a2", name: "Sales Researcher", current_version: 1, model: "claude-sonnet-4-6",
    description: "Researches prospects on the web and drafts tailored outreach.",
    n_tools: 3, n_skills: 0, n_kbs: 0, n_sub_agents: 0, auto_improve: false, tags: ["sales"] },
  { id: "a3", name: "Ops Team", current_version: 2, model: "claude-opus-4-8",
    description: "Coordinator that delegates to billing, logistics and reporting specialists.",
    n_tools: 1, n_skills: 0, n_kbs: 0, n_sub_agents: 3, auto_improve: true, tags: ["ops"] },
  { id: "a4", name: "SQL Helper", current_version: 1, model: "claude-haiku-4-5",
    description: "Writes and explains SQL against your schema notes.",
    n_tools: 2, n_skills: 1, n_kbs: 1, n_sub_agents: 0, auto_improve: false, tags: ["data"] },
  { id: "a5", name: "Shopify Concierge", current_version: 1, model: "claude-sonnet-4-6",
    description: "Looks up products and orders via the Shopify connector.",
    n_tools: 4, n_skills: 0, n_kbs: 0, n_sub_agents: 0, auto_improve: false, tags: ["sales"] },
  { id: "a6", name: "Doc Summarizer", current_version: 5, model: "claude-haiku-4-5",
    description: "Summarizes long PDFs into crisp briefs with citations.",
    n_tools: 1, n_skills: 2, n_kbs: 1, n_sub_agents: 0, auto_improve: true, tags: ["research"] },
];

const RUNS = [
  { id: "r1", kind: "ask", status: "done", agent_id: "a1", agent_name: "Support Concierge", created_at: ago(3) },
  { id: "r2", kind: "ask", status: "done", agent_id: "a5", agent_name: "Shopify Concierge", created_at: ago(18) },
  { id: "r3", kind: "ask", status: "error", agent_id: "a2", agent_name: "Sales Researcher", created_at: ago(46) },
  { id: "r4", kind: "ask", status: "done", agent_id: "a6", agent_name: "Doc Summarizer", created_at: ago(95) },
  { id: "r5", kind: "build", status: "done", agent_id: "a5", agent_name: "Shopify Concierge", created_at: ago(140) },
  { id: "r6", kind: "ask", status: "done", agent_id: "a4", agent_name: "SQL Helper", created_at: ago(210) },
];

const TOOLS = [
  { name: "kb.search", description: "Search the attached knowledge base.", source: "builtin" },
  { name: "calc.eval", description: "Scientific calculator.", source: "builtin" },
  { name: "web.scrape", description: "Fetch a page and return readable text.", source: "builtin" },
  { name: "http.fetch", description: "HTTP GET a URL.", source: "builtin" },
  { name: "fs.write", description: "Write a workspace file.", source: "builtin" },
  { name: "shopify.get_products", description: "List Shopify products.", source: "plugin", plugin_key: "shopify", plugin_name: "Shopify" },
  { name: "shopify.search_orders", description: "Search Shopify orders.", source: "plugin", plugin_key: "shopify", plugin_name: "Shopify" },
];

const PLUGINS = [
  { id: "p1", key: "shopify", name: "Shopify", description: "Storefront / Admin commerce.",
    kind: "mcp", transport: "http", url: "https://demo-shop.myshopify.com/api/mcp", args: [],
    tool_allowlist: [], header_names: ["Authorization"], enabled: true, status: "ok", n_tools: 6 },
  { id: "p2", key: "alibaba", name: "Alibaba", description: "Sourcing & product data.",
    kind: "mcp", transport: "http", url: "https://demo-alibaba-mcp.example.com/mcp", args: [],
    tool_allowlist: [], header_names: ["Authorization"], enabled: false, status: "unknown", n_tools: 0 },
];

const TEMPLATES = [
  { key: "shopify", name: "Shopify", icon: "🛍️", transport: "http", description: "Products, orders, customers via Shopify's MCP.", url_placeholder: "https://your-shop.myshopify.com/api/mcp", auth: { header: "Authorization", prefix: "Bearer ", label: "Access token" } },
  { key: "alibaba", name: "Alibaba", icon: "📦", transport: "http", description: "Alibaba / 1688 sourcing via a configured MCP endpoint.", url_placeholder: "https://your-alibaba-mcp.example.com/mcp", auth: { header: "Authorization", prefix: "Bearer ", label: "API key" } },
  { key: "custom-http", name: "Custom HTTP / SSE", icon: "🔌", transport: "http", description: "Any Streamable-HTTP or SSE MCP server.", url_placeholder: "https://host/mcp", auth: { header: "Authorization", prefix: "Bearer ", label: "Token (optional)" } },
  { key: "custom-stdio", name: "Local (stdio)", icon: "💻", transport: "stdio", description: "Run a local MCP server process.", command_placeholder: "npx", args_placeholder: "-y some-mcp-server", auth: null },
];

const KBS = [
  { id: "kb1", name: "Help Center", description: "Product docs & FAQs", retrieval_mode: "hybrid", vector_store: "pgvector", document_count: 12 },
  { id: "kb2", name: "Schema Notes", description: "Database schema reference", retrieval_mode: "semantic", vector_store: "qdrant", document_count: 3 },
];

const FIXTURES: Record<string, unknown> = {
  "/api/setup/status": { needs_setup: false, completed: true, auth_enabled: true,
    workspace_name: "Mevrik AI", llm_provider: "anthropic", embed_provider: "auto", embed_dim: 1536 },
  "/api/auth/me": { authenticated: true, auth_enabled: true,
    user: { id: "u1", email: "ada@mevrik.tech", name: "Ada Lovelace", role: "admin" },
    workspace: { id: "w1", name: "Mevrik AI" } },
  "/api/auth/users": [
    { id: "u1", email: "ada@mevrik.tech", name: "Ada Lovelace", role: "admin", is_active: true },
    { id: "u2", email: "grace@mevrik.tech", name: "Grace Hopper", role: "member", is_active: true },
  ],
  "/api/auth/invites": [],
  "/api/config": { llm_provider: "anthropic", orchestrator_model: "claude-opus-4-8",
    worker_model: "claude-sonnet-4-6", embed_provider: "auto", embed_dim: 1536,
    vector_store: "pgvector", env: "local", role: "admin" },
  "/api/agents": AGENTS,
  "/api/agent-tags": ["support", "sales", "ops", "data", "research"],
  "/api/runs": RUNS,
  "/api/tools": TOOLS,
  "/api/plugins": PLUGINS,
  "/api/plugins/templates": TEMPLATES,
  "/api/skills": [
    { id: "s1", name: "cite-pages", description: "Always cite the source page", content: "# Cite pages\n" },
    { id: "s2", name: "tone-friendly", description: "Warm, concise tone", content: "# Friendly tone\n" },
  ],
  "/api/kb": KBS,
  "/api/analytics": {
    totals: { runs: 248, agents: AGENTS.length, cost_usd: 1.42, tokens: 1_284_000 },
    success_rate: 0.94, avg_latency_ms: 1850,
  },
};

export function installDemo(mode = ""): void {
  // `?demo=setup` previews the first-run wizard (no session, fresh workspace).
  if (mode === "setup") {
    localStorage.removeItem("veldra.token");
    FIXTURES["/api/setup/status"] = {
      needs_setup: true, completed: false, auth_enabled: true,
      workspace_name: "Veldra", llm_provider: "anthropic", embed_provider: "auto", embed_dim: 1536,
    };
  } else if (mode !== "signin") {
    localStorage.setItem("veldra.token", "demo-token");
  } else {
    localStorage.removeItem("veldra.token");
  }
  const real = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    if (path in FIXTURES) {
      return new Response(JSON.stringify(FIXTURES[path]), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    if (path.startsWith("/api/")) {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }
    return real(input, init);
  };
}
