# Blank Template

A full-stack template with a React frontend and FastAPI backend.

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
git clone https://github.com/ProbablyFaiz/blank.git <your-project-name>
cd <your-project-name>
```

**Customize the project name:**
- Recommended: Use VSCode's find/replace (Ctrl+Shift+H) with "Preserve Case" enabled
- Replace all instances of `blank` with your project name
- Update `backend/pyproject.toml` project name and description
- Update `frontend/package.json` name field

### 2. Install Dependencies

```bash
just install
```

This installs:
- Pre-commit hooks (will also install `pre-commit` as a user-wide `uv` tool)
- Python dependencies in a virtual environment via `uv`
- Frontend dependencies via `pnpm`

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
  ./infra/create_admin_db_user.fish <your_admin_user> <your_database>
  ./infra/create_api_db_user.fish <your_api_user> <your_database>
  ```

### 4. Start Development

**Terminal 1 - Backend:**
```bash
just api
```

**Terminal 2 - Frontend:**
```bash
just frontend
```

Your app will be available at:
- Frontend: http://localhost:5185
- Backend API: http://localhost:8101
- API Docs: http://localhost:8101/docs

### 5. Run Tests

To ensure all tests are passing, run:

## Available Commands

### Development
- `just api` - Start FastAPI backend server
- `just frontend` - Start Vite development server
  - Note that the dev server must be running for Tanstack Router's route tree to automatically re-generate when you change routes
- `just openapi` - Regenerate API client from backend OpenAPI spec
- `just shadd <component>` - Add a shadcn/ui component; equivalent to `pnpm dlx shadcn@latest add <component>`

### Building & Quality
- `just build` - Build frontend for production
- `just lint` - Run pre-commit hooks (formatting, linting)
- `just typecheck` - Run TypeScript type checking

### Testing

To run frontend tests:
```bash
just test-frontend
# Or, to run a specific test file:
just test-frontend <path to test file, relative to frontend/>
# E.g.,
just test-frontend src/features/home/HomePage.test.tsx
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

TODO

## Project Structure

```
├── backend/           # FastAPI backend
│   ├── blank/         # Main package (rename this!)
│   │   ├── api/       # API routes & endpoints
│   │   ├── db/        # Database models, sessions & migrations
│   │   ├── jobs/      # Background job processing (Celery)
│   │   └── utils/     # Shared utilities (observability, storage)
│   ├── test/          # Backend tests
│   └── pyproject.toml # Python dependencies
├── frontend/          # React frontend
│   ├── src/
│   │   ├── routes/    # TanStack Router routes
│   │   ├── features/  # Feature-based components
│   │   ├── components/# Shared components & shadcn/ui
│   │   ├── client/    # Generated API client
│   │   └── lib/       # Utility functions
│   └── package.json   # Frontend dependencies
├── docs/              # Documentation
├── infra/             # Infrastructure scripts (DB setup)
├── .github/workflows/ # CI/CD workflows
├── docker-compose.yml # Multi-container setup
└── Justfile           # Task automation
```

**Note on Authentication:** This template doesn't include authentication by default. For production apps, we recommend Auth0 with `fastapi-auth0` (backend) and `@auth0/auth0-react` (frontend).

## Tech Stack

**Frontend:**
- [React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/) + [Vite](https://vite.dev/)
- [TanStack Router](https://tanstack.com/router/latest/docs/framework/react/overview) for routing
- [shadcn/ui](https://ui.shadcn.com/) + [Tailwind CSS](https://tailwindcss.com/) for styling
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview) for API state management
- [openapi-ts](https://github.com/hey-api/openapi-ts) for API client generation
  - Word for the wise: upgrade with extreme caution. It seems like every release has significant breaking changes.

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
- Docker/Docker Compose for building and running the application
- Cloudflare Tunnel acts as a reverse proxy for the application to expose it to the internet


## TODOs

- Add instructions for setting up the production deployment
- Add Playwright tests
  - We'll probably want to set up a whole docker-compose.test.yml file for this to make it CI-friendly
- Add more than Sentry for observability
- Add some kind of optional auth boilerplate
- Refactor `rl` library to accept a `RL_ENV_PREFIX` environment (e.g. `RL_ENV_PREFIX=BLANK_`) so that we can place
  bucket and Postgres utils in that package rather than copy-pasting them into each project via a template
