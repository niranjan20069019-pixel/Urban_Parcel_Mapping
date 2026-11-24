.PHONY: install dev start stop migrate test lint docker-up docker-down setup

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

setup:
	python scripts/validate_environment.py
	python scripts/setup.py

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

test:
	cd backend && pytest tests/ -v

migrate:
	cd backend && python -c "from app.db.database import init_db; import asyncio; asyncio.run(init_db())"

pipeline:
	python scripts/run_pipeline.py
