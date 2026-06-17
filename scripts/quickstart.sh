#!/usr/bin/env bash
# Veldra quickstart — one command from zero to a running app.
# Checks prereqs, pulls the local models, brings up the stack, waits for health.
set -euo pipefail
cd "$(dirname "$0")/.."

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
die()  { printf "  \033[31m✗ %s\033[0m\n" "$1"; exit 1; }

bold "Veldra quickstart"

# 1. Docker
command -v docker >/dev/null 2>&1 || die "Docker is required — install Docker Desktop, then re-run."
docker info >/dev/null 2>&1 || die "Docker is installed but the daemon isn't running — start Docker, then re-run."
ok "Docker is running"

# 2. Ollama + models (local-first default; skip if you'll use a cloud provider)
OLLAMA_MODEL="${VELDRA_OLLAMA_MODEL:-qwen3.5:0.8b}"
EMBED_MODEL="${VELDRA_OLLAMA_EMBED_MODEL:-nomic-embed-text}"
if command -v ollama >/dev/null 2>&1 && curl -sf --max-time 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
  for m in "$OLLAMA_MODEL" "$EMBED_MODEL"; do
    if ollama list 2>/dev/null | awk '{print $1}' | grep -qx "$m"; then ok "model $m present";
    else warn "pulling $m …"; ollama pull "$m"; ok "pulled $m"; fi
  done
else
  warn "Ollama not detected — that's fine if you'll use OpenAI/Anthropic (set VELDRA_LLM_PROVIDER in .env)."
fi

# 3. .env
[ -f .env ] || { cp example.env .env; ok "created .env from example.env"; }
ok ".env ready"

# 4. bring up the stack
bold "Starting the stack (this builds the app image on first run)…"
docker compose -f deploy/docker-compose.yml up --build -d

# 5. wait for health
printf "  waiting for the API"
for _ in $(seq 1 90); do
  if curl -sf --max-time 2 http://localhost:8000/api/health >/dev/null 2>&1; then printf " ready\n"; HEALTHY=1; break; fi
  printf "."; sleep 2
done
echo
if [ "${HEALTHY:-}" = "1" ]; then
  bold "Veldra is up → http://localhost:8000"
  echo "  First run shows the install wizard: name your workspace, test the provider, create the admin."
  echo "  Stop with: make down   ·   Logs: make logs"
else
  warn "API didn't report healthy yet — check 'make logs' (the image may still be building)."
fi
