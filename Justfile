set dotenv-load

# Default recipe to run when just is called without arguments
default:
    just --list

# First-time setup: install prek, git hooks, and all dependencies
init:
    uv tool install prek
    prek install
    just install

# Install all dependencies
install:
    cd backend && uv venv --python 3.11 && uv sync
    cd frontend-static && pnpm install

# Open a pgcli shell as the admin DB user
sql:
    cd backend && uv run pgcli "postgresql://$FANTASY_COURT_PG_ADMIN_USER:$FANTASY_COURT_PG_ADMIN_PASSWORD@$FANTASY_COURT_PG_HOST:$FANTASY_COURT_PG_PORT/$FANTASY_COURT_PG_DB"

# Start the FastAPI backend development server
api *ARGS:
    cd backend && uv run fastapi dev court/api/main.py --host 0.0.0.0 --port 8203 {{ARGS}}

# Start the celery dev worker
celery *ARGS:
    cd backend && uv run celery -A court.jobs.celery:celery_app worker --loglevel=info {{ARGS}}

# Build the static site for production
build:
    cd frontend-static && pnpm build

# Regenerate the OpenAPI client types (requires a running API)
openapi *HOST:
    cd frontend-static && pnpm run openapi {{HOST}}

# Run all lint and format hooks
lint:
    prek run --all-files

# Typecheck the frontend
typecheck-frontend:
    cd frontend-static && pnpm typecheck

# Typecheck the backend
typecheck-backend:
    cd backend && uv run ty check --exit-zero-on-warning

# Typecheck frontend and backend
typecheck: typecheck-frontend typecheck-backend

# Run backend tests (optionally a single file, relative to backend/)
test-backend *ARGS:
    cd backend && uv run pytest {{ARGS}}

# Run all tests
test: test-backend

# Generate a migration with the provided message
migrate *ARGS:
    #!/usr/bin/env fish
    cd backend
    and uv run alembic revision --autogenerate -m "{{ARGS}}"
    and echo (set_color yellow)"Run "(set_color cyan)"just migrate-up"(set_color yellow)" to apply the migration."(set_color normal)

# Generate an empty migration with the provided message
migrate-blank *ARGS:
    cd backend && uv run alembic revision -m "{{ARGS}}"

# Apply all migrations
migrate-up:
    cd backend && uv run alembic upgrade head

# Rollback the last migration
migrate-down:
    cd backend && uv run alembic downgrade -1

# Deploy the application
deploy:
    git pull && docker compose up --build -d
