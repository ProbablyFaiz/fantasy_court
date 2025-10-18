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
    cd ../frontend && pnpm install

sql:
    cd backend && uv run pgcli "postgresql://$BLANK_PG_ADMIN_USER:$BLANK_PG_ADMIN_PASSWORD@$BLANK_PG_HOST:$BLANK_PG_PORT/$BLANK_PG_DB"

# Start the FastAPI backend development server
api *ARGS:
    cd backend && uv run fastapi dev blank/api/main.py --host 0.0.0.0 --port 8101 {{ARGS}}

# Start the frontend development server
frontend *ARGS:
    cd frontend && VITE_BLANK_API_URL="http://poirot:8101" pnpm dev --host 0.0.0.0 --port 5186 {{ARGS}}

# Start the celery dev worker
celery *ARGS:
    cd backend && uv run celery -A blank.jobs.celery:celery_app worker --loglevel=info {{ARGS}}

# Build the frontend for production
build:
    cd frontend && pnpm build

# Regenerate the OpenAPI client
openapi *HOST:
    cd frontend && pnpm run openapi {{HOST}}

# Run pre-commit hooks
lint:
    pre-commit run --all-files

# Run frontend typechecking
typecheck:
    cd frontend && pnpm run typecheck

# Add a shadcn/ui component
shadd *ARGS:
    cd frontend && pnpm dlx shadcn@latest add {{ARGS}}

# Run frontend tests
test-frontend *ARGS:
    cd frontend && pnpm test:run {{ARGS}}

# Run backend tests
test-backend *ARGS:
    cd backend && uv run pytest {{ARGS}}

# Run all tests
test-all:
    just test-frontend
    just test-backend

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
