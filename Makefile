# Veldra — one-command management.
COMPOSE = docker compose -f deploy/docker-compose.yml

.PHONY: up down logs ps restart build migrate dev help quickstart

help:
	@echo "Veldra:"
	@echo "  make quickstart  zero-to-running: check prereqs, pull models, start, wait for health"
	@echo "  make up          build + start the whole stack (UI+API → http://localhost:8000)"
	@echo "  make down        stop everything"
	@echo "  make logs        tail the app logs"
	@echo "  make restart     restart just the app"
	@echo "  make dev         run backend + web with hot-reload (host mode)"

quickstart:        ## One command from zero to a running app.
	@bash scripts/quickstart.sh

.env:
	cp example.env .env

up: .env            ## Build + start the entire stack in one command.
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Veldra is up → http://localhost:8000   (needs Ollama running on the host)"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f app

ps:
	$(COMPOSE) ps

restart:
	$(COMPOSE) up -d --build app

# Host-mode dev (hot reload): infra in Docker, app + web on the host.
dev: .env
	$(COMPOSE) up -d postgres redis minio createbuckets
	uv run python -m veldra_app.db migrate
	@echo "Run in two terminals:  uv run uvicorn veldra_app.main:app --reload  |  (cd apps/web && npm run dev)"
