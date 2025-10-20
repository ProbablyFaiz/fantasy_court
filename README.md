# Fantasy Court

An official-seeming court website for *The Ringer Fantasy Football Show*'s Fantasy Court podcast segment. Uses AI to transcribe episodes, extract fantasy football dispute cases, and generate legal-style opinions with a Next.js static site and FastAPI backend.

## Prerequisites

- **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **just** task runner (`uv tool install rust-just`)
- **Node.js 18+**
- **pnpm** (`npm install -g pnpm`)
- **PostgreSQL**
- **Redis**

For deployment:
- **Docker**/**Docker Compose**

## Quick Start

### 1. Clone and Customize

```bash
git clone https://github.com/ProbablyFaiz/fantasy_court.git fantasy_court
cd fantasy_court
```

### 2. Install Dependencies

```bash
just install
```

This installs:
- Pre-commit hooks (will also install `pre-commit` as a user-wide `uv` tool)
- Python dependencies in a virtual environment via `uv`
- Frontend-static dependencies via `pnpm`

If you need more granular control over your environment setup, see the `just install` definition in `Justfile` for a starting point.

### 3. Configure Environment

```bash
cp template.env .env
mkdir data
```

Edit `.env` and fill in the variables:
- Set `DATA_ROOT` to the absolute path of your `data` directory
- Configure PostgreSQL connection details
- For database credentials, use the helper scripts in `infra/` to create users:
  ```bash
  ./infra/create_admin_db_user.fish <your_admin_user> fantasy_court
  ./infra/create_api_db_user.fish <your_api_user> fantasy_court
  ```

### 4. Start Development

**Backend:**
```bash
just api
```

Backend API will be available at:
- Backend API: http://localhost:8203
- API Docs: http://localhost:8203/docs

**Frontend (Static Site):**
The frontend is a statically generated Next.js site. To build it locally:
```bash
cd frontend-static
pnpm run build
```

### 5. Run Tests

To ensure all tests are passing, run:

## Available Commands

### Development
- `just api` - Start FastAPI backend server

### Building & Quality
- `just lint` - Run pre-commit hooks (formatting, linting)
- `just typecheck` - Run TypeScript type checking on frontend-static

### Testing

To run frontend tests:
```bash
just test-frontend
# Or, to run a specific test file:
just test-frontend <path to test file, relative to frontend-static/>
# E.g.,
just test-frontend src/components/AudioPlayer.test.tsx
```

To run backend tests:
```bash
just test-backend
# Or, to run a specific test file:
just test-backend <path to test file, relative to backend/>
# E.g.,
just test-backend test/api/test_tasks_api.py
```

To run all tests:
```bash
just test-all
```
### Database
- `just migrate "description"` - Generate new Alembic migration
- `just migrate-up` - Apply pending migrations
- `just migrate-down` - Rollback last migration

### Shortcuts
- `just` - Show all available commands
- `just install` - Install all dependencies (frontend + backend)


## Production Deployment

The Fantasy Court pipeline runs as a scheduled Celery task that:
1. Ingests new podcast episodes from the RSS feed
2. Downloads episode audio files to S3
3. Detects and transcribes Fantasy Court segments
4. Extracts cases and drafts judicial opinions using AI
5. Exports opinions to JSON format
6. Builds the Next.js static site
7. Deploys to Cloudflare Pages

See `court/pipeline/commands.py` for the full pipeline implementation.

## Project Structure

```
├── backend/              # FastAPI backend
│   ├── court/            # Main package
│   │   ├── api/          # API routes & endpoints
│   │   ├── db/           # Database models, sessions & migrations
│   │   ├── inference/    # AI inference scripts (segments, cases, opinions)
│   │   ├── ingest/       # Episode ingestion & processing
│   │   ├── export/       # Data export utilities
│   │   ├── pipeline/     # Automated pipeline orchestration
│   │   ├── jobs/         # Background job processing (Celery)
│   │   └── utils/        # Shared utilities (observability, storage)
│   ├── test/             # Backend tests
│   └── pyproject.toml    # Python dependencies
├── frontend-static/      # Next.js static site
│   ├── src/
│   │   ├── pages/        # Next.js pages
│   │   ├── components/   # React components
│   │   └── client/       # Generated API client types
│   ├── public/           # Static assets
│   │   └── data/         # JSON data for static generation
│   └── package.json      # Frontend dependencies
├── docs/                 # Documentation
├── infra/                # Infrastructure scripts (DB setup)
├── .github/workflows/    # CI/CD workflows
├── docker-compose.yml    # Multi-container setup
└── Justfile              # Task automation
```

## Tech Stack

**Frontend:**
- [Next.js](https://nextjs.org/) (Static Site Generation) + [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Tailwind CSS](https://tailwindcss.com/) for styling
- [openapi-ts](https://github.com/hey-api/openapi-ts) for API client type generation

**Backend:**
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/) 2.x ORM + [Alembic](https://alembic.sqlalchemy.org/en/latest/) migrations
- [PostgreSQL](https://www.postgresql.org/) database
- [Pydantic](https://docs.pydantic.dev/) 2.x for data validation

**Observability:**
- [Sentry](https://sentry.io/) for error tracking on both frontend and backend (optional)

**Tools:**
- [just](https://github.com/casey/just) for task automation
- [pnpm](https://pnpm.io/) for frontend package management
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- **Code Quality**: Pre-commit hooks with [Ruff](https://github.com/astral-sh/ruff) (Python) and [Biome](https://biomejs.dev/) (TypeScript/JavaScript)

**Production Deployment:**
- Docker/Docker Compose for backend services
- Cloudflare Pages for static site hosting
- Automated pipeline via Celery for content processing and deployment
