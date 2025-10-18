# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
## Commands
- Run all tests: `cd backend && pytest`
- Run frontend typechecking: `just typecheck`
- Run backend (Python) tests: `just test-backend`
    - Run single test file: `just test-backend <path to test file relative to backend/>` e.g., `just test-backend test/api/test_tasks_api.py`
- Run frontend (TS) tests: `just test-frontend`
    - Run single test file: `just test-frontend <path to test file relative to frontend/>` e.g., `just test-frontend src/features/home/HomePage.test.tsx`
- Add a shadcn/ui component: `just shadd <component>` (equivalent to `pnpm dlx shadcn@latest add <component>`)

- Format code: `just lint`
  - Often helpful to run this after making large code changes.
- Generate OpenAPI client: `just openapi` (regenerates frontend/src/client from running API)
- Generate (but do not run) DB migrations based on changes to backend/perm/db/models.py: `just migrate "message"` (auto-generate)
    - Please use `just migrate` and then modify the alembic migration as necessary, do not try to create one from scratch manually.
    - Remember when creating migrations for non-nullable columns that if they are for an existing table, you will probably need to
    modify the migration to first create the column as nullable, initialize the column's values appropriately, and then set it to
    non-nullable.
- You should not, unless instructed, run the API or frontend dev servers; the developer is almost certainly already running them, and you doing so will just be harmful.

Note that, as shown, to run code in the backend Python environment, one must run `uv run <your python command>`
inside the `backend/` directory. The `just` shortcuts handle this for you when they are available.

YOU ARE ABSOLUTELY PROHIBITED FROM EXECUTING THE MIGRATION YOU HAVE GENERATED YOURSELF. DO NOT RUN `just migrate-up` OR
`alembic upgrade ...` or `alembic downgrade ...` UNDER ANY CIRCUMSTANCES. IF RUNNING A MIGRATION IS NECESSARY FOR THE
CONTINUATION OF WORK, ASK THE USER TO PERFORM IT.

## Pull Requests

When writing PR descriptions, be concise! It is unnecessary to bullet list every change in detail;
give the core changes. Most importantly, a PR should prominently highlight things which are important
for other developers to know: for instance, database migrations should be highlighted, any new environment
variables that they may want or need to set, etc. Remember: be concise, the purpose of these PRs is to
be communicative and not just a list of changes.

## Testing Philosophy
- **Avoid mocks** - Use real database models and the existing PostgreSQL testing infrastructure
- **Use fixtures** - Create proper object graphs with pytest fixtures to avoid repetition and ensure foreign key constraints are satisfied
- **Test behavior, not implementation** - Focus on what the code does, not how it does it
- **Be pragmatic** - Write tests that give confidence in critical functionality without over-testing trivial code

## Backend Development
- Typing is very important, so be sure to type any function arguments/outputs.
  - In Python, the lowercase types (e.g. 'list', 'dict') should be used where available instead of importing from the typing package. Note that lowercase types do not need to be imported.
  - Use `SomeType | None` instead of `Optional[SomeType]`.
- Pathlib Paths should be used over the equivalent os functions.
- Use SQLAlchemy 2.x ORM syntax, not 1.x.
  - E.g., you should write queries as `db.execute(<query var or the query inline>).scalars().all()` instead of `db.query(Model).all()`.
  - Some helpful context: my projects are typically structured such that models are in <project_name>.db.models, and you can create a session with `from <project_name>.db.session import get_session` (e.g. `from cdle.db.session`) and then `session = get_session()`.
- Use Pydantic 2.x syntax, not 1.x.
- Prefer Pydantic models over dataclasses when applicable.
- Prefer full imports for lowercase (non-class, usually) symbols, e.g. `import tenacity ... @tenacity.retry` or `import tqdm ... tqdm.tqdm()`, and `from` imports for uppercase constants and classes, e.g., `from blank.db.models import Chunk, CHUNK_SEPARATOR`.
- Lazy imports (that is, imports not at the top of the file) are ABSOLUTELY PROHIBITED, unless necessary to avoid a circular import.

### Writing Standalone Scripts
- We like progress bars! *Long-running, important* loops should use a tqdm progress bar with appropriate concise desc parameter set. When postfixes are necessary (e.g. if tracking the number of records skipped in some loop operation), define a `pbar` variable separately, and then update it and set the postfix within the loop manually.
- To avoid confusion, always do "import tqdm" and then "tqdm.tqdm" for the progress bar instead of "from tqdm import tqdm". Repeat, use `import tqdm` and `tqdm.tqdm(...)` in code, NEVER `from tqdm import tqdm` and `tqdm(...)`.
### Using the `rl` Utility Library
When writing Python scripts, we have a utility library called `rl`. Some notes on `rl` and the way we use it:
- We have an enhanced version of click, the Python CLI library. The only difference in usage from the regular click is one does `import rl.utils.click as click` instead of `import click`.
- When using logging in a program, use `rl`'s preconfigured logger: `from rl.utils import LOGGER`.
- `rl` has (among others) the following IO functions, usable within `import rl.utils.io` (do not `from import`, use the absolute import):
    - `def get_data_path(*args) -> Path` — Generally, whenever a CLI script deals with input and output files/dirs, the default paths (which should typically be configurable via CLI options) are set on some subpath of the data path. E.g. `_DEFAULT_OUTPUT_DIR = rl.utils.io.get_data_path("raw_codes", "sf")`.
    - `def read_jsonl(filename: str | Path) -> Iterable[Any]` — yield an iterable of JSON-parsed items from a JSONL file, used as `for record in rl.utils.io.read_jsonl(...):` etc. If loading JSONL records into Pydantic models, you can also do `rl.utils.io.read_jsonl(..., pydantic_cls=<pydantic_model>)` to iterate the records into a Pydantic model instances.
    - `def download(url: str, dest: str | Path) -> None` — Downloads a given url to a file with a progress bar, so when doing pure downloads this is preferable.

### Creating Click CLIs
When creating click CLIs, obey the following conventions:
- Unless otherwise instructed, prefer options, not arguments. Provide concise and descriptive help text for each option. Provide both a long (--foo) and short (-f) for all options unless doing so would lead to a conflict.
- Default values for options should be stored as private global constants (`_ALL_CAPS`) at the top of the file and then referenced (`default=_DEFAULT_INPUT_PATH`) in the option decorator.
- When declaring options that refer to file paths or directories, file paths should be suffixed with '_path', while directory paths should be suffixed with '_dir'. Path options should always be declared with `type=click.Path([any applicable exists/okay options], path_type=Path)` and the resulting function argument should therefore be typed as a pathlib `Path`.


### FastAPI API Development
The API endpoints, interfaces, and dependencies are contained within the `backend/blank/api` directory.

- All endpoints should be decorated with the `response_model` and an `operation_id` (in camel case, e.g. `listEvalIssues`). GET endpoints which return paginated lists should be named as list{plural object in camel case} (e.g. `listEvalIssues` with return type `PaginatedBase[EvalIssueItem]`), for single objects, `read{singular object in camel case}`, e.g. `readEvalIssue` with return type `EvalIssueRead`.
- When declaring endpoint dependencies, use the Annotated syntax, e.g., `db: Annotated[Session, Depends(get_db)]`, NOT the `= Depends(get_db)` default argument syntax.
- Words in urls should be separated by underscores, not dashes. E.g. `issue_histories` not `issue-histories`.
- By convention, list endpoints should return a paginated object using the PaginatedBase generic in backend/blank/api/interfaces.py. Here is an example:
- When writing dependencies for the API in `backend/blank/api/deps.py`, you should be sure to eager-load any related models (via `.options` on the query) that will be sent as part of the defined interface in `backend/blank/api/interfaces.py`. In almost 100% of cases, the correct approach is `selectinload`; `joinedload` has unpredictable and sometimes dire performance consequences.
- When defining interfaces, typically follow the convention of defining a model's `<model_name>Base` with the small and direct fields of a model, a `<model_name>Read` which is the full-fat version of the model that we would by convention return from a `read<model_name>` endpoint that has any of the related objects as well. And a `<model_name>Item` interface that would typically be returned in a related object's list child. E.g. a `ProjectRead` might have a `permit_applications` field which is typed as `list[PermitApplicationItem]`.
    - This is a general practice but not a hard rule, and we can depart from it where particular items require related objects; the direct fields contain a large blob that should be omitted; etc.

Example endpoint excerpt:
```python
@router.get(
    "/tasks", response_model=PaginatedBase[TaskItem], operation_id="listTasks"
)
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    project_id: Annotated[int | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    query = (
        # omitted
    )

    if project_id is not None:
        ...  # omitted

    if search is not None:
        ...  # omitted

    query = (
       ...  # omitted
    )
    tasks = db.execute(query).scalars().all()

    return PaginatedBase(
        items=tasks,
        total=total,
        page=page,
        size=limit,
    )
```

## Frontend Development
- When using React, we use Typescript and typically build most UI elements with Tailwind/shadcn
    - Please use shadcn components where available or installable. When asked to use icons, use Lucide icons.
- When designing UI, you should build components that are aesthetically pleasing, modern in design, and consistent with the app's existing conventions.
- Generally speaking, import project files relative to the src directory using the `@/` alias, e.g. `@/features/home/CTA.tsx`
### API Client Usage (React Query)
Our API client is auto-generated and provides TanStack Query (React Query) integration:
- Import types from `@/client` (e.g., `import { TaskListItem } from "@/client"`)
- Import services like `DefaultService` from `@/client`
- Import query options from `@/client/@tanstack/react-query.gen`
API endpoint naming convention follows these patterns:
- GET endpoints for single items generate `readXOptions` functions (e.g., `readTaskOptions`)
- GET endpoints for paginated lists generate `listXOptions` functions (e.g., `listTaskRunPredictionsOptions`)
- Query keys are available as `readXQueryKey` and `listXQueryKey` functions with the same arguments as the `readXOptions` functions.
When using the client with React Query:
- For read operations, spread the options from the generated functions:
  ```typescript
  const { data } = useQuery({
    ...readTaskOptions({ path: { task_id: taskId } }),
  });
