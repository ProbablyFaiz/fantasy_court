"""Draft Fantasy Court opinions with a Claude Code agent working in a file workspace.

For each case we materialize a workspace (see court.law.workspace), point a
headless Claude Code session at it with permissions bypassed, let it grep the
corpus and write opinion/, lint the result, and save it to the database.
"""

import asyncio
import dataclasses
import os
import tempfile
from pathlib import Path

import rl.utils.click as click
import sqlalchemy as sa
import tqdm
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from rich.table import Table
from sqlalchemy.orm import Session, selectinload

from court.db.models import (
    FantasyCourtCase,
    FantasyCourtOpinion,
    FantasyCourtSegment,
    PodcastEpisode,
)
from court.db.session import get_session
from court.inference.utils import get_or_create_provenance
from court.law import lint as lint_module
from court.law import workspace as workspace_module
from court.utils.print import CONSOLE

_DEFAULT_MODEL = "claude-fable-5-1"
_DEFAULT_CONCURRENCY = 4
_CREATOR_NAME = "claude-fable-5-1"
_TASK_NAME = "create_opinions"
_RECORD_TYPE = "fantasy_court_opinions"

_MAX_TURNS = 150
_CLAUDE_CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
_EFFORT = "medium"
_MAX_LINT_ROUNDS = 2
_CASE_TIMEOUT_S = 1800

_DRAFT_PROMPT = """Draft the Fantasy Court opinion for the case in this workspace.

Read CLAUDE.md first; it is the complete style guide and workflow. Read case.md and transcript.txt, research precedent in corpus/, write the four files in opinion/, do a genuine revision pass on your draft, and run ./lint until it reports no errors. When you are done, reply with a short summary of the opinion and what you changed in revision."""

_LINT_FIX_PROMPT = """./lint still reports errors on opinion/:

{report}

Fix them, run ./lint again, and confirm it passes."""


def _uses_subscription() -> bool:
    """True when a claude.ai login or long-lived OAuth token is available."""
    return _CLAUDE_CREDENTIALS_PATH.exists() or bool(
        os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    )


def _agent_env() -> dict[str, str]:
    env = {
        # Server-side context management is not available to every org;
        # the CLI otherwise requests it for models that support it.
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
    }
    # The CLI lets ANTHROPIC_API_KEY take precedence over the claude.ai login,
    # which bills the API instead of the subscription. Hide it when a login
    # exists (local runs); Docker has no login and falls back to the key.
    if _uses_subscription():
        env["ANTHROPIC_API_KEY"] = ""
    return env


def _serialize_messages(messages: list) -> list[dict]:
    """Serialize SDK messages into JSON-compatible dicts for agent_message_log."""
    serialized = []
    for message in messages:
        if dataclasses.is_dataclass(message):
            record = {"type": type(message).__name__, **dataclasses.asdict(message)}
        else:
            record = {"type": type(message).__name__, "repr": repr(message)}
        serialized.append(record)
    return serialized


def _tool_use_summary(block: ToolUseBlock) -> str:
    """One-line description of a tool call for the console."""
    inputs = block.input
    for key in ("command", "file_path", "pattern", "description"):
        if key in inputs:
            return f"{block.name} {inputs[key]}"
    return block.name


def _print_message(message: object, label: str) -> None:
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ThinkingBlock):
                CONSOLE.print(
                    f"[dim yellow]{label} thinking:[/dim yellow] [dim]{block.thinking}[/dim]"
                )
            elif isinstance(block, TextBlock):
                CONSOLE.print(f"[cyan]{label}:[/cyan] {block.text}")
            elif isinstance(block, ToolUseBlock):
                CONSOLE.print(
                    f"[green]{label} tool:[/green] {_tool_use_summary(block)}"
                )
    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.2f}" if message.total_cost_usd else "n/a"
        if _uses_subscription():
            cost += " nominal, billed to subscription"
        CONSOLE.print(
            f"[magenta]{label} result:[/magenta] {message.subtype}, "
            f"{message.num_turns} turns, cost {cost}"
        )


async def _run_session(
    client: ClaudeSDKClient, prompt: str, label: str, log: list
) -> ResultMessage:
    await client.query(prompt)
    result: ResultMessage | None = None
    async for message in client.receive_response():
        log.append(message)
        _print_message(message, label)
        if isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise RuntimeError("Agent session ended without a result message")
    if result.is_error:
        raise RuntimeError(f"Agent session failed: {result.subtype}: {result.result}")
    return result


async def run_opinion_drafting_agent(
    db: Session,
    model: str,
    case: FantasyCourtCase,
    workspace_dir: Path | None = None,
) -> FantasyCourtOpinion:
    """Draft an opinion for a case and return it (not yet added to the session).

    The case must have its episode and segment (with transcript) loaded. If
    workspace_dir is None, a temporary directory is used and discarded.
    """
    label = case.docket_number
    with tempfile.TemporaryDirectory(prefix=f"court-{label}-") as tmp:
        workspace = workspace_dir or Path(tmp)
        workspace_module.create_workspace(db, workspace, case)
        auth = "claude.ai subscription" if _uses_subscription() else "API key"
        CONSOLE.print(
            f"[bold blue]{label}[/bold blue] {case.case_caption or '(no caption)'} "
            f"[dim]workspace {workspace}, auth {auth}[/dim]"
        )

        options = ClaudeAgentOptions(
            cwd=str(workspace),
            model=model,
            permission_mode="bypassPermissions",
            setting_sources=["project"],
            disallowed_tools=["WebFetch", "WebSearch"],
            max_turns=_MAX_TURNS,
            effort=_EFFORT,
            env=_agent_env(),
        )
        log: list = []
        async with ClaudeSDKClient(options=options) as client:
            await _run_session(client, _DRAFT_PROMPT, label, log)
            result = lint_module.lint_workspace(workspace)
            for _ in range(_MAX_LINT_ROUNDS):
                if result.ok:
                    break
                CONSOLE.print(f"[yellow]{label} lint:[/yellow]\n{result.render()}")
                await _run_session(
                    client,
                    _LINT_FIX_PROMPT.format(report=result.render()),
                    label,
                    log,
                )
                result = lint_module.lint_workspace(workspace)
        if not result.ok:
            raise ValueError(f"Opinion failed lint after fixes:\n{result.render()}")
        if result.warnings:
            CONSOLE.print(f"[yellow]{label} lint warnings:[/yellow]\n{result.render()}")

        fields = workspace_module.read_opinion_files(workspace)
        return FantasyCourtOpinion(
            case_id=case.id,
            agent_message_log=_serialize_messages(log),
            **fields,
        )


async def process_cases_batch(
    cases: list[FantasyCourtCase],
    db: Session,
    provenance_id: int,
    model: str,
    concurrency: int,
) -> tuple[int, int]:
    """Draft opinions for cases in chronological batches of size `concurrency`.

    Each batch is committed before the next starts so later opinions can cite
    earlier ones. Returns (opinions_created, cases_processed).
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(case: FantasyCourtCase) -> FantasyCourtOpinion | None:
        async with semaphore:
            try:
                opinion = await asyncio.wait_for(
                    run_opinion_drafting_agent(db, model, case),
                    timeout=_CASE_TIMEOUT_S,
                )
                opinion.provenance_id = provenance_id
                return opinion
            except Exception as e:
                CONSOLE.print(
                    f"[red]Error processing case {case.id} (docket {case.docket_number}):[/red] {e}"
                )
                return None

    total_created = 0
    failed_count = 0
    pbar = tqdm.tqdm(total=len(cases), desc="Drafting opinions")
    for i in range(0, len(cases), concurrency):
        batch = cases[i : i + concurrency]
        batch_results = await asyncio.gather(*(process_one(case) for case in batch))
        batch_opinions = [opinion for opinion in batch_results if opinion is not None]
        failed_count += len(batch) - len(batch_opinions)
        if batch_opinions:
            db.add_all(batch_opinions)
            db.commit()
            total_created += len(batch_opinions)
        pbar.update(len(batch))
    pbar.close()

    if failed_count > 0:
        CONSOLE.print(
            f"\n[yellow]Warning:[/yellow] {failed_count} case(s) failed to process\n"
        )
    return total_created, len(cases)


@click.command()
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_MODEL,
    help="Claude model to use for opinion drafting",
)
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=_DEFAULT_CONCURRENCY,
    help="Number of agents to run in parallel",
)
def main(model: str, concurrency: int):
    """Draft Fantasy Court opinions for every case that lacks one."""
    CONSOLE.print(
        f"\n[bold blue]Drafting Fantasy Court opinions using:[/bold blue] {model}"
    )
    CONSOLE.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}\n")

    db = get_session()
    provenance = get_or_create_provenance(db, _TASK_NAME, _CREATOR_NAME, _RECORD_TYPE)
    db.commit()

    cases_query = (
        sa.select(FantasyCourtCase)
        .join(
            FantasyCourtSegment, FantasyCourtCase.segment_id == FantasyCourtSegment.id
        )
        .join(FantasyCourtSegment.transcript)
        .join(FantasyCourtCase.episode)
        .outerjoin(
            FantasyCourtOpinion, FantasyCourtCase.id == FantasyCourtOpinion.case_id
        )
        .where(FantasyCourtOpinion.id.is_(None))
        .options(
            selectinload(FantasyCourtCase.episode),
            selectinload(FantasyCourtCase.segment).selectinload(
                FantasyCourtSegment.transcript
            ),
        )
        # To develop the common law sequentially, we order by pub_date ascending
        .order_by(PodcastEpisode.pub_date.asc())
    )
    cases = list(db.execute(cases_query).scalars().all())
    CONSOLE.print(f"[bold]Found {len(cases)} cases with transcripts but no opinions.\n")
    if not cases:
        CONSOLE.print("[yellow]No cases to process[/yellow]\n")
        return

    opinions_created, cases_processed = asyncio.run(
        process_cases_batch(cases, db, provenance.id, model, concurrency)
    )
    CONSOLE.print(
        f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{opinions_created}[/bold cyan] "
        f"opinions from [bold]{cases_processed}[/bold] cases processed\n"
    )

    if opinions_created > 0:
        table = Table(title="Created Opinions", show_header=True, header_style="bold")
        table.add_column("Docket", style="cyan")
        table.add_column("Caption", style="green")
        table.add_column("Authorship", style="magenta")
        recent_opinions = (
            db.execute(
                sa.select(FantasyCourtOpinion)
                .options(selectinload(FantasyCourtOpinion.case))
                .where(FantasyCourtOpinion.provenance_id == provenance.id)
                .order_by(FantasyCourtOpinion.created_at.desc())
                .limit(opinions_created)
            )
            .scalars()
            .all()
        )
        for opinion in recent_opinions:
            table.add_row(
                opinion.case.docket_number,
                opinion.case.case_caption or "(no caption)",
                workspace_module.html_to_text(opinion.authorship_html),
            )
        CONSOLE.print(table)
        CONSOLE.print()


if __name__ == "__main__":
    main()
