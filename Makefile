.PHONY: up down build seed forecast test lint format migrate shell logs

# Docker
up:
	docker compose up -d --build
	@echo "Services starting... check status with: make logs"

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=100

# Database
migrate:
	docker compose exec api alembic upgrade head

migrate-create:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

# Data
seed:
	docker compose exec api python src/scripts/seed_synthetic.py

# Forecast
forecast:
	@echo "Triggering forecast run..."
	curl -s -X POST http://localhost:8000/forecasts \
	  -H "Content-Type: application/json" \
	  -d '{"triggered_by": "manual"}' | python3 -m json.tool

# Dev
shell:
	docker compose exec api bash

# Python quality
lint:
	ruff check src/ tests/
	mypy src/

format:
	black src/ tests/
	ruff check --fix src/ tests/

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

# Install dev deps locally (for IDE support)
install-dev:
	uv pip install -e ".[dev]"
	pre-commit install
