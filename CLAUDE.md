# CLAUDE.md / AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) or other agents when working with code in this repository.

There is one very important rule: no emojis in code or strings, ever. You must obey this rule above all other priorities.

## Project Context

Fantasy Court is an official-seeming court website for *The Ringer Fantasy Football Show*'s Fantasy Court podcast segment. A Python pipeline ingests podcast episodes, transcribes the Fantasy Court segment, extracts the disputes as "cases", and drafts legal-style opinions with an LLM. The opinions are exported to JSON and rendered by a statically generated Next.js site deployed to Cloudflare Pages. The whole pipeline runs on a schedule as a Celery task; see `backend/court/pipeline/commands.py`.

This is a personal project. Keep changes proportionate; do not build infrastructure the project does not need.

**STOP. READ THIS BEFORE TOUCHING GIT.** You are ABSOLUTELY PROHIBITED from running `git stash` (push OR pop), `git reset`, `git checkout <branch>`, `git checkout .`, `git checkout -- <path>`, `git restore`, `git clean`, `git switch`, or ANY other command that moves, discards, hides, or rewrites uncommitted changes or the current branch. This applies even "temporarily", even "just to check something", even if you plan to immediately undo it, even if you think the working tree is clean, and even if you think you'll restore state perfectly afterward. You will not. If you need to inspect another branch, ASK THE USER FIRST, or use a fresh `git worktree add` in a separate directory -- never the live worktree. If you need to temporarily set aside changes, ASK. Violating this rule is treated as a serious failure regardless of intent or outcome.

## Commands
- Run backend tests: `just test-backend`
    - Run a single test file: `just test-backend <path relative to backend/>`, e.g. `just test-backend test/api/test_episodes_api.py`
- Typecheck frontend and backend: `just typecheck`
    - Backend only (ty): `just typecheck-backend`
    - Frontend only (tsc): `just typecheck-frontend`
- Format and lint everything: `just lint` (runs the prek hooks: ruff and Biome)
  - Often helpful to run this after making large code changes.
- Regenerate the OpenAPI client types: `just openapi`. This reads the spec from a running API at localhost:8203, so only run it if the developer confirms the API is up.
- Generate (but do not run) DB migrations based on changes to `backend/court/db/models.py`: `just migrate "message"`
    - Use `just migrate` and then modify the alembic migration as necessary; do not write one from scratch.
    - When adding a non-nullable column to an existing table, modify the migration to first create the column as nullable, backfill it, and then set it to non-nullable.

**WARNING: Alembic autogenerate does NOT track CHECK constraints!** If you add, modify, or remove a `sa.CheckConstraint` in `models.py` on an existing table, you MUST manually add the corresponding `op.create_check_constraint()` or `op.drop_constraint()` call to the migration.

- Do not run the API dev server (`just api`) or the celery worker unless instructed; the developer is almost certainly already running them.

To run code in the backend Python environment, run `uv run <command>` inside `backend/`. The `just` shortcuts handle this for you when they are available.

YOU ARE ABSOLUTELY PROHIBITED FROM EXECUTING THE MIGRATION YOU HAVE GENERATED YOURSELF. DO NOT RUN `just migrate-up` OR
`alembic upgrade ...` or `alembic downgrade ...` UNDER ANY CIRCUMSTANCES. IF RUNNING A MIGRATION IS NECESSARY FOR THE
CONTINUATION OF WORK, ASK THE USER TO PERFORM IT.

Generally speaking, you should not run the tests after making changes to the code unless you are asked to do so. If you are asked to draft a new script from scratch, you should typically not run the script yourself (import tests and smaller verifications are alright, but side-effectful full script runs are frowned upon) unless the user or context calls for it. The inference scripts in particular call paid LLM APIs and write to the database.

## Pull Requests
When writing PR descriptions, be concise! It is unnecessary to bullet list every change in detail;
give the core changes. Most importantly, a PR should prominently highlight things which are important
for other developers to know: for instance, database migrations should be highlighted, any new environment
variables that they may want or need to set, etc.

## Testing Philosophy
- **Avoid mocks** - Use real database models and the existing PostgreSQL testing infrastructure. Mock only at true boundaries (LLM APIs, external services). Do NOT create fake/shim classes to mimic SQLAlchemy models.
- **Use fixtures** - Create proper object graphs with pytest fixtures to avoid repetition and ensure foreign key constraints are satisfied.
- **Test behavior, not implementation** - Focus on what the code does, not how it does it. Tests should survive refactoring.
- **Don't over-test** - Not everything needs a test. Ask: is this logic complex enough to break?
- **Keep tests fast** - Individual test files should run in seconds.
- **Consolidate related assertions** - One test can verify multiple related behaviors.
- **Write robust tests** - Where order is not a factor in correctness, test inclusion rather than position.

### Test Directory Structure
Tests live in `backend/test/` and mirror the source layout:
- `backend/test/conftest.py` - Shared fixtures: `db_session` (sync SQLAlchemy session on an ephemeral pytest-postgresql database, rolled back after each test) and `client` (FastAPI `TestClient` with `get_db` overridden to use `db_session`)
- `backend/test/factories.py` - Factory Boy factories for creating test data
- `backend/test/<module>/test_<file>.py` - Tests for `backend/court/<module>/<file>.py`

### Writing Backend Tests
- Sessions are synchronous. Build objects with factories (`.build()`), `db_session.add()` them, and `db_session.commit()` or `flush()` to get IDs.
- Check `court/db/models.py` for required fields and foreign keys before writing fixtures. `FantasyCourtCase` requires an episode, a segment, and a provenance.
- Do not hit `/health` or `/error` in tests; they dispatch Celery tasks.

## Backend Development
- Typing is very important, so be sure to type any function arguments/outputs.
  - In Python, the lowercase types (e.g. 'list', 'dict') should be used where available instead of importing from the typing package.
  - Use `SomeType | None` instead of `Optional[SomeType]`.
- Pathlib Paths should be used over the equivalent os functions. For instance, use `path.open()` instead of `open(path)`.
- Use SQLAlchemy 2.x ORM syntax, not 1.x.
  - E.g., write queries as `db.execute(<query>).scalars().all()` instead of `db.query(Model).all()`.
  - Sessions are sync. `court.db.session.get_session()` returns an admin-credentialed session for scripts and the pipeline; the API uses `get_api_session()` via the `get_db` dependency.
- Use Pydantic 2.x syntax, not 1.x.
- Prefer Pydantic models over dataclasses when applicable.
- Prefer full imports for lowercase (non-class, usually) symbols, e.g. `import tenacity ... @tenacity.retry` or `import tqdm ... tqdm.tqdm()`, and `from` imports for uppercase constants and classes, e.g. `from court.db.models import FantasyCourtCase`.
- Lazy imports (that is, imports not at the top of the file) are ABSOLUTELY PROHIBITED, unless necessary to avoid a circular import.
- LLM model IDs are module-level `_DEFAULT_MODEL` constants in `court/inference/*.py`, overridable via the `--model` CLI option. The Anthropic calls use adaptive thinking; do not add `budget_tokens` or forced `tool_choice`.

### CLI Structure
The CLI is registered in `pyproject.toml` as `court = "court.cli.main:cli"`. Invoke as `uv run court ...` from `backend/`. It follows a modular architecture:

- **Main entry point**: `backend/court/cli/main.py` creates the base `cli` group and imports/registers all command groups
- **Convention**: Each functional area has a `commands.py` file (e.g. `court/inference/commands.py`, `court/ingest/commands.py`) that defines a click group with related commands
- **Registration**: Command groups are imported in `main.py` and added via `cli.add_command(group_name)`
- **Implementation**: Business logic lives in separate modules within each area; `commands.py` files contain only CLI definitions and should serve as a thin, but useful wrapper to quickly invoke the underlying business logic.

### Writing Standalone Scripts
- We like progress bars! *Long-running, important* loops should use a tqdm progress bar with an appropriate concise `desc`. When postfixes are necessary, define a `pbar` variable separately, then update it and set the postfix within the loop manually.
- Always `import tqdm` and use `tqdm.tqdm(...)`, NEVER `from tqdm import tqdm`.
- Experimental/debug/probe scripts go in `backend/court/experiments/`, not a top-level `scripts/` directory. Run them with `uv run python -m court.experiments.<name>` from `backend/`. This directory is excluded from typechecking.

### Using the `rl` Utility Library
`rl` is a shared utility library (a git dependency). Conventions:
- Enhanced click: `import rl.utils.click as click` instead of `import click`.
- Logging: `from rl.utils import LOGGER`.
- IO helpers, used via `import rl.utils.io` (never `from` imports):
    - `rl.utils.io.getenv(name)` - environment variables. Config is read at module import time in `court/db/session.py`, `court/db/redis.py`, `court/utils/bucket.py`, and `court/utils/observe.py`; there is no settings object.
    - `rl.utils.io.get_data_path(*args) -> Path` - paths under `DATA_ROOT`. Default input/output paths for CLI scripts should live here, e.g. `_DEFAULT_OUTPUT_DIR = rl.utils.io.get_data_path("exports")`.
    - `rl.utils.io.read_jsonl(path, pydantic_cls=...)` - iterate JSONL records, optionally into Pydantic models.
    - `rl.utils.io.download(url, dest)` - download with a progress bar.
- Use `beautifulsoup4` with `lxml` for HTML/XML parsing rather than `html.parser` or `xml.etree`.

### Creating Click CLIs
- Prefer options, not arguments. Provide concise help text for each option. Provide both a long (`--foo`) and short (`-f`) form unless doing so would lead to a conflict.
- Default values for options should be stored as private global constants (`_ALL_CAPS`) at the top of the file and referenced (`default=_DEFAULT_INPUT_PATH`) in the option decorator.
- File path options are suffixed `_path`, directory options `_dir`. Declare them with `type=click.Path([exists/okay options], path_type=Path)` and type the argument as `Path`.
- **Never truncate output** in CLI display; show full content.
- **Avoid rich Panels**; use plain `CONSOLE.print()` with markup (`court.utils.print.CONSOLE`).

### FastAPI API Development
The API lives in `backend/court/api/`: `main.py` (app and all routes), `interfaces.py` (Pydantic response models), `deps.py` (`get_db` and resource-fetching dependencies). Routes stay in `main.py` until it becomes unwieldy. The API is read-only and exists to feed the static site export and local inspection.

- All endpoints must set `response_model` and a camelCase `operation_id`. Paginated GET lists are `list{Plural}` (e.g. `listEpisodes`) returning `PaginatedBase[XItem]`; single objects are `read{Singular}` (e.g. `readEpisode`) returning `XRead`.
- Declare dependencies with the Annotated syntax, e.g. `db: Annotated[Session, Depends(get_db)]`, NOT `= Depends(get_db)`.
- Words in URLs are separated by underscores, not dashes.
- Eager-load related models in `deps.py` with `selectinload` for anything the interface serializes. Avoid `joinedload` except for one-to-one relationships on single-resource fetches.
- Interfaces follow `<Model>Base` (direct fields), `<Model>Read` (full object with related objects, returned by `read<Model>`), and `<Model>Item` (compact form used inside lists and as a child of other interfaces).

#### Return Type Conventions
`response_model` is always a Pydantic interface; the function returns the ORM object directly and lets FastAPI serialize it. Do not call `model_validate()` in endpoints.

```python
@app.get(
    "/episodes/{episode_id}",
    response_model=EpisodeRead,
    operation_id="readEpisode",
)
def read_episode(
    episode: Annotated[PodcastEpisode, Depends(get_episode)],
):
    return episode
```

#### Resource-fetching dependencies
Every endpoint that loads a single ORM object uses a dependency in `deps.py` (`get_episode`, `get_case`, `get_opinion`) that takes the path param plus `db`, applies the eager-load policy for that resource, and 404s if missing. Reuse the dependency rather than writing inline loads.

#### Interface and ORM mirroring
Interfaces are strict subsets of the ORM model. Mirror relationships as nested objects (`case: CaseItem`), not flattened ids and names. Put computed values on the ORM model as `@property` (traversing already-loaded relationships), not in endpoints.

## Frontend Development
`frontend-static/` is a Next.js app with `output: "export"`; there is no server. Pages read pre-exported JSON from `public/data/` (written by `court export opinions`) at build time. Deploys are a `pnpm build` followed by `wrangler pages deploy`.

- TypeScript, React 19, Tailwind v4 with CSS-based configuration (no `tailwind.config.js`). Use Lucide for icons.
- Import project files with the `@/` alias, e.g. `@/components/OpinionPage`.
- Types for exported data come from `@/client` (`types.gen.ts`, generated by openapi-ts from the API spec). There is no runtime API client and no React Query; do not add data fetching to the site.
- Use `pnpm`, never `npm` or `yarn`.
- Biome (config at the repo root) handles lint and format; run `just lint`.

## File Reading
Err on the side of reading entire files or large (100+ lines) blocks of code at a time. If the user tags a file, read the entire file.
