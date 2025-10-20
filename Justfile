set dotenv-load

# Default recipe to run when just is called without arguments
default:
    just --list

# Install all dependencies
install:
    #!/usr/bin/env fish
    uv tool install pre-commit
    pre-commit install

    cd backend && uv venv --python 3.11 && uv sync
    cd frontend-static && pnpm install


# Start the FastAPI backend development server
api *ARGS:
    cd backend && uv run fastapi dev court/api/main.py --host 0.0.0.0 --port 8203 {{ARGS}}

# Start the celery dev worker
celery *ARGS:
    cd backend && uv run celery -A court.jobs.celery:celery_app worker --loglevel=info {{ARGS}}

# Build the frontend for production
build:
    cd frontend-static && pnpm build

# Regenerate the OpenAPI client
openapi *HOST:
    cd frontend-static && pnpm run openapi {{HOST}}

# Run pre-commit hooks
lint:
    pre-commit run --all-files


# Generate a migration with the provided message
migrate *ARGS:
    #!/usr/bin/env fish
    cd backend
    and uv run alembic revision --autogenerate -m "{{ARGS}}"
    and echo (set_color yellow)"Run "(set_color cyan)"just migrate-up"(set_color yellow)" to apply the migration."(set_color normal)

# Apply all migrations
migrate-up:
    cd backend && uv run alembic upgrade head

# Rollback the last migration
migrate-down:
    cd backend && uv run alembic downgrade -1

# Deploy the application
deploy:
    git pull && docker compose up --build -d
