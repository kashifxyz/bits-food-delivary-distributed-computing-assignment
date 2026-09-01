.PHONY: install test test-unit test-integration run-backend run-frontend run-all clean docker-up docker-down

install:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && pnpm install

test:
	PYTHONPATH=. backend/.venv/bin/pytest backend/tests/ -v

test-unit:
	PYTHONPATH=. backend/.venv/bin/pytest backend/tests/unit/ -v

test-integration:
	PYTHONPATH=. backend/.venv/bin/pytest backend/tests/integration/ -v

run-backend:
	./scripts/start_backend.sh

run-frontend:
	./scripts/start_frontend.sh

run-all:
	./scripts/start_all.sh

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	./scripts/clean.sh
