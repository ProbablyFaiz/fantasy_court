# Fantasy Court

An official-seeming court website for *The Ringer Fantasy Football Show*'s Fantasy Court podcast segment. Uses AI to transcribe episodes, extract fantasy football dispute cases, and generate legal-style opinions, rendered by a Next.js static site generated from a Python / PostgreSQL backend.

## Prerequisites

- **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **just** task runner (`uv tool install rust-just`)
- **Node.js 22+**
- **pnpm** (`npm install -g pnpm`)
- **PostgreSQL** (a local server for development; the test suite spawns its own via `pytest-postgresql`, which needs the PostgreSQL binaries on `PATH`)
- **Redis**

For deployment:
- **Docker**/**Docker Compose**

## Quick Start

### 1. Clone

```bash
git clone https://github.com/ProbablyFaiz/fantasy_court.git fantasy_court
cd fantasy_court
```

### 2. Install Dependencies

```bash
just init
```

This installs:
- `prek` (as a user-wide `uv` tool) and the git pre-commit hooks
- Python dependencies in a virtual environment via `uv`
- Frontend dependencies via `pnpm`

Use `just install` on subsequent runs to skip the hook setup.

### 3. Configure Environment

```bash
cp template.env .env
mkdir data
```

Edit `.env` and fill in the variables:
- Set `DATA_ROOT` to the absolute path of your `data` directory
- Configure PostgreSQL connection details
- Create the two database roles with the helper scripts in `infra/`:
  ```bash
  ./infra/create_admin_db_user.py <your_admin_user> fantasy_court
  ./infra/create_api_db_user.py <your_api_user> fantasy_court
  ```

### 4. Start Development

**Backend:**
```bash
just api
```

- API: http://localhost:8203
- Docs: http://localhost:8203/docs

**Frontend (static site):**
```bash
just build
```

The site reads exported opinion JSON from `frontend-static/public/data/`. Populate it with `uv run court export opinions` from `backend/`.

### 5. Checks

```bash
just lint       # ruff + Biome via prek
just typecheck  # ty (backend) and tsc (frontend)
just test       # backend pytest
```

## Available Commands

Run `just` to list everything. The main ones:

- `just api` - Start the FastAPI dev server
- `just celery` - Start a Celery worker
- `just build` - Build the static site
- `just openapi` - Regenerate `frontend-static/src/client` types from the running API
- `just lint` / `just typecheck` / `just test` - Quality checks (see above)
- `just test-backend <path>` - Run a single backend test file
- `just migrate "description"` - Generate an Alembic migration
- `just migrate-up` / `just migrate-down` - Apply / roll back migrations
- `just sql` - Open a `pgcli` shell as the admin user
- `just deploy` - Pull and rebuild the Docker Compose stack

## Production Deployment

The backend runs as two Docker Compose services, a Celery worker and Celery beat, attached to the shared `infra` network where PostgreSQL and Redis live (see `docker-compose.yml`). Runtime secrets come from a `prod.env` file next to the compose file.

The scheduled pipeline task:
1. Ingests new podcast episodes from the RSS feed
2. Downloads episode audio files to the bucket
3. Detects and transcribes Fantasy Court segments
4. Extracts cases and drafts judicial opinions using AI
5. Exports opinions to JSON
6. Builds the Next.js static site
7. Deploys it to Cloudflare Pages

See `backend/court/pipeline/commands.py` for the full pipeline implementation.

## Project Structure

```
├── backend/              # FastAPI backend and pipeline
│   ├── court/            # Main package
│   │   ├── api/          # API routes, interfaces, and deps
│   │   ├── db/           # Database models, sessions, and migrations
│   │   ├── inference/    # AI inference (segments, cases, opinions, citations)
│   │   ├── ingest/       # Episode ingestion and audio download
│   │   ├── export/       # JSON export for the static site
│   │   ├── pipeline/     # Automated pipeline orchestration
│   │   ├── jobs/         # Celery app, tasks, and schedule
│   │   ├── experiments/  # One-off scripts (excluded from typechecking)
│   │   └── utils/        # Shared utilities (bucket, observability, printing)
│   ├── test/             # Backend tests
│   └── pyproject.toml    # Python dependencies and tool config
├── frontend-static/      # Next.js static site
│   ├── src/
│   │   ├── pages/        # Next.js pages
│   │   ├── components/   # React components
│   │   └── client/       # Generated API types
│   └── public/data/      # Exported JSON consumed at build time (gitignored)
├── docs/                 # Design notes
├── infra/                # DB role setup scripts
├── .github/workflows/    # CI: prek, backend typecheck + tests, frontend build
├── docker-compose.yml    # Production services
└── Justfile              # Task runner
```

## Tech Stack

**Frontend:**
- [Next.js](https://nextjs.org/) static export + [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/) v4
- [openapi-ts](https://github.com/hey-api/openapi-ts) for API type generation

**Backend:**
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.x + [Alembic](https://alembic.sqlalchemy.org/en/latest/) migrations
- [PostgreSQL](https://www.postgresql.org/)
- [Celery](https://docs.celeryq.dev/) + Redis for the scheduled pipeline
- [Pydantic](https://docs.pydantic.dev/) 2.x

**Observability:**
- [Sentry](https://sentry.io/) for backend error tracking (optional, set `FANTASY_COURT_SENTRY_DSN`)

**Tooling:**
- [just](https://github.com/casey/just), [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/)
- [prek](https://github.com/j178/prek) hooks running [Ruff](https://github.com/astral-sh/ruff) and [Biome](https://biomejs.dev/)
- [ty](https://github.com/astral-sh/ty) for Python typechecking

**Deployment:**
- Docker Compose for the Celery services
- Cloudflare Pages for the static site
