.PHONY: run dev test lint format docker-up docker-down

run:
	uvicorn main:api --host 0.0.0.0 --port 8000

dev:
	uvicorn main:api --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v --cov=.

lint:
	flake8 .
	mypy .

format:
	black .
	isort .

docker-up:
	docker-compose up --build -d
