import asyncio
import difflib
import re

import anthropic
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
from anthropic import AsyncAnthropic
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from sqlalchemy.orm import Session, selectinload

from court.db.models import FantasyCourtOpinion
from court.db.session import get_session
from court.inference.create_opinions import _SYSTEM_PROMPT as _OPINION_DRAFTING_PROMPT
from court.utils.print import CONSOLE

_ANTHROPIC_API_KEY = rl.utils.io.getenv("ANTHROPIC_API_KEY")

_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

_SYSTEM_PROMPT = f"""You are an editor for Fantasy Court opinions.

Your role is to help refine and improve Fantasy Court opinions while maintaining their legal style, humor, and adherence to precedent.

You can help with:
- Improving clarity and readability
- Ensuring proper legal citation format
- Maintaining consistency with existing opinions
- Refining legal reasoning
- Improving prose quality
- Ensuring proper HTML formatting

For context, here is the prompt given to the opinion drafting agent:
```
{_OPINION_DRAFTING_PROMPT}
```

Always maintain the formal legal tone while preserving the dry wit and deadpan humor characteristic of Fantasy Court opinions.

## File System Structure

You have access to a virtual file system for editing Fantasy Court opinions:

- `/opinions/` - Lists all available opinions with their IDs, docket numbers, and captions
- `/opinions/<id>/` - Lists the editable files for a specific opinion

**Opinion Fields (editable):**
- `/opinions/<id>/authorship.html` - The authorship statement (who wrote the opinion, who joined, who dissented)
- `/opinions/<id>/holding_statement.html` - The holding statement (the "Held:" summary)
- `/opinions/<id>/reasoning_summary.html` - The reasoning summary (2-4 sentence framework)
- `/opinions/<id>/opinion_body.html` - The full opinion body (the main content)

**Case Fields (editable):**
- `/opinions/<id>/case_caption.txt` - The case caption
- `/opinions/<id>/fact_summary.txt` - Summary of the facts
- `/opinions/<id>/questions_presented.html` - The legal questions presented
- `/opinions/<id>/procedural_posture.txt` - How the case arrived at the court

Note: The docket number is not editable and is only shown in directory listings.

## Important Notes

- DO NOT use the `create` command - all opinions already exist in the database
- Use `view` to examine opinions and case information
- Use `str_replace` to make precise edits to opinion content
- Use `insert` to add new content at specific line numbers
- When editing, ensure you maintain proper HTML formatting and legal citation style
- All changes are automatically saved to the database

## Example workflow

To edit an opinion:
1. Start by viewing `/opinions/` to see all available opinions
2. View `/opinions/<id>/` to see what files are available for that opinion
3. View the specific file you want to edit, e.g., `/opinions/<id>/opinion_body.html`
4. Use `str_replace` to make precise edits
5. View the file again to verify your changes
"""


def _format_opinion_list(db: Session) -> str:
    """Format a list of all opinions for directory listing."""
    opinions = (
        db.execute(
            sa.select(FantasyCourtOpinion)
            .options(selectinload(FantasyCourtOpinion.case))
            .order_by(FantasyCourtOpinion.id)
        )
        .scalars()
        .all()
    )

    if not opinions:
        return "No opinions found in database."

    lines = [f"Fantasy Court Opinions ({len(opinions)} total)\n"]
    lines.append("=" * 80)
    lines.append("")

    for opinion in opinions:
        case = opinion.case
        lines.append(f"Opinion ID: {opinion.id}")
        lines.append(f"  Docket: {case.docket_number}")
        lines.append(f"  Caption: {case.case_caption or '(no caption)'}")
        lines.append(f"  Path: /opinions/{opinion.id}/")
        lines.append("")

    return "\n".join(lines)


def _format_opinion_directory(opinion: FantasyCourtOpinion) -> str:
    """Format the directory listing for a specific opinion."""
    case = opinion.case

    lines = [f"Opinion {opinion.id}: {case.case_caption or '(no caption)'}"]
    lines.append(f"Docket: {case.docket_number}")
    lines.append("")
    lines.append("Opinion Files (editable):")
    lines.append("  authorship.html")
    lines.append("  holding_statement.html")
    lines.append("  reasoning_summary.html")
    lines.append("  opinion_body.html")
    lines.append("")
    lines.append("Case Files (editable):")
    lines.append("  case_caption.txt")
    lines.append("  fact_summary.txt")
    lines.append("  questions_presented.html")
    lines.append("  procedural_posture.txt")

    return "\n".join(lines)


def _parse_opinion_path(path: str) -> tuple[int | None, str | None]:
    """
    Parse an opinion path into (opinion_id, filename).

    Returns:
        (opinion_id, filename) or (None, None) if invalid

    Examples:
        "/opinions/" -> (None, None)
        "/opinions/5/" -> (5, None)
        "/opinions/5/authorship.html" -> (5, "authorship.html")
        "/opinions/5/case_caption.txt" -> (5, "case_caption.txt")
    """
    # Normalize path
    path = path.strip().rstrip("/")

    # Handle root opinions directory
    if path == "/opinions" or path == "":
        return (None, None)

    # Match patterns like /opinions/5 or /opinions/5/authorship.html
    match = re.match(r"^/opinions/(\d+)(?:/(.+))?$", path)
    if not match:
        return (None, None)

    opinion_id = int(match.group(1))
    filename = match.group(2) or None

    return (opinion_id, filename)


def _handle_view_command(
    db: Session, path: str, view_range: list[int] | None = None
) -> str:
    """Handle a view command and return the file/directory contents."""
    opinion_id, filename = _parse_opinion_path(path)

    # List all opinions
    if opinion_id is None:
        return _format_opinion_list(db)

    # Load the opinion
    opinion = db.execute(
        sa.select(FantasyCourtOpinion)
        .where(FantasyCourtOpinion.id == opinion_id)
        .options(selectinload(FantasyCourtOpinion.case))
    ).scalar_one_or_none()

    if not opinion:
        return f"Error: Opinion {opinion_id} not found"

    # Show directory listing for this opinion
    if filename is None:
        return _format_opinion_directory(opinion)

    case = opinion.case

    # Map all files (both opinion and case fields)
    content_map = {
        # Opinion fields
        "authorship.html": opinion.authorship_html,
        "holding_statement.html": opinion.holding_statement_html,
        "reasoning_summary.html": opinion.reasoning_summary_html,
        "opinion_body.html": opinion.opinion_body_html,
        # Case fields (editable)
        "case_caption.txt": case.case_caption or "(no caption)",
        "fact_summary.txt": case.fact_summary,
        "questions_presented.html": case.questions_presented_html or "(none)",
        "procedural_posture.txt": case.procedural_posture or "(none)",
    }

    if filename not in content_map:
        return f"Error: Unknown file '{filename}'"

    content = content_map[filename]

    # Apply view_range if specified
    if view_range is not None:
        lines = content.split("\n")
        start, end = view_range

        # Handle 1-indexed lines and -1 for end
        start = max(0, start - 1) if start > 0 else 0
        end = len(lines) if end == -1 else min(len(lines), end)

        content = "\n".join(lines[start:end])

    return content


def _handle_str_replace_command(
    db: Session, path: str, old_str: str, new_str: str
) -> str:
    """Handle a str_replace command and update the database."""
    opinion_id, filename = _parse_opinion_path(path)

    if opinion_id is None:
        return "Error: Cannot edit the opinions directory"

    if filename is None:
        return "Error: Must specify a file to edit"

    # Load the opinion
    opinion = db.execute(
        sa.select(FantasyCourtOpinion)
        .where(FantasyCourtOpinion.id == opinion_id)
        .options(selectinload(FantasyCourtOpinion.case))
    ).scalar_one_or_none()

    if not opinion:
        return f"Error: Opinion {opinion_id} not found"

    case = opinion.case

    # Map filename to model and attribute
    opinion_fields = {
        "authorship.html": (opinion, "authorship_html"),
        "holding_statement.html": (opinion, "holding_statement_html"),
        "reasoning_summary.html": (opinion, "reasoning_summary_html"),
        "opinion_body.html": (opinion, "opinion_body_html"),
    }

    case_fields = {
        "case_caption.txt": (case, "case_caption"),
        "fact_summary.txt": (case, "fact_summary"),
        "questions_presented.html": (case, "questions_presented_html"),
        "procedural_posture.txt": (case, "procedural_posture"),
    }

    if filename in opinion_fields:
        model_obj, field_name = opinion_fields[filename]
    elif filename in case_fields:
        model_obj, field_name = case_fields[filename]
    else:
        return f"Error: Unknown file '{filename}'"

    current_content = getattr(model_obj, field_name) or ""

    # Perform the replacement
    if old_str not in current_content:
        return f"Error: The specified text was not found in {filename}"

    new_content = current_content.replace(old_str, new_str, 1)

    # Generate a unified diff to show the changes
    old_lines = current_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{filename} (before)",
        tofile=f"{filename} (after)",
        lineterm="",
        n=3,  # 3 lines of context
    )

    diff_text = "\n".join(diff)

    # Update the database
    setattr(model_obj, field_name, new_content)
    db.commit()

    # Return success message with diff
    if diff_text:
        return f"Successfully replaced text in {filename}. Changes saved to database.\n\n{diff_text}"
    else:
        return f"Successfully replaced text in {filename}. Changes saved to database."


def _handle_insert_command(
    db: Session, path: str, insert_line: int, new_str: str
) -> str:
    """Handle an insert command and update the database."""
    opinion_id, filename = _parse_opinion_path(path)

    if opinion_id is None:
        return "Error: Cannot edit the opinions directory"

    if filename is None:
        return "Error: Must specify a file to edit"

    # Load the opinion
    opinion = db.execute(
        sa.select(FantasyCourtOpinion)
        .where(FantasyCourtOpinion.id == opinion_id)
        .options(selectinload(FantasyCourtOpinion.case))
    ).scalar_one_or_none()

    if not opinion:
        return f"Error: Opinion {opinion_id} not found"

    case = opinion.case

    # Map filename to model and attribute
    opinion_fields = {
        "authorship.html": (opinion, "authorship_html"),
        "holding_statement.html": (opinion, "holding_statement_html"),
        "reasoning_summary.html": (opinion, "reasoning_summary_html"),
        "opinion_body.html": (opinion, "opinion_body_html"),
    }

    case_fields = {
        "case_caption.txt": (case, "case_caption"),
        "fact_summary.txt": (case, "fact_summary"),
        "questions_presented.html": (case, "questions_presented_html"),
        "procedural_posture.txt": (case, "procedural_posture"),
    }

    if filename in opinion_fields:
        model_obj, field_name = opinion_fields[filename]
    elif filename in case_fields:
        model_obj, field_name = case_fields[filename]
    else:
        return f"Error: Unknown file '{filename}'"

    current_content = getattr(model_obj, field_name) or ""

    # Split into lines and insert
    lines = current_content.split("\n")

    # insert_line=0 means beginning of file
    if insert_line < 0 or insert_line > len(lines):
        return f"Error: Invalid line number {insert_line} (file has {len(lines)} lines)"

    # Insert after line insert_line (0 means before first line)
    lines.insert(insert_line, new_str)

    new_content = "\n".join(lines)
    setattr(model_obj, field_name, new_content)

    # Commit to database
    db.commit()

    return f"Successfully inserted text at line {insert_line} in {filename}. Changes saved to database."


def _remove_cache_controls(messages: list[dict]) -> None:
    """
    Remove cache_control from all content blocks in the message history.

    This modifies the messages list in-place. We need to do this before adding
    a new cache_control to avoid exceeding Anthropic's limit of 4 cache_control blocks.
    """
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "cache_control" in item:
                    del item["cache_control"]


def _process_tool_use(db: Session, tool_input: dict) -> str:
    """Process a tool use and return the result."""
    command = tool_input.get("command")

    if command == "view":
        path = tool_input.get("path", "")
        view_range = tool_input.get("view_range")
        return _handle_view_command(db, path, view_range)

    elif command == "str_replace":
        path = tool_input.get("path", "")
        old_str = tool_input.get("old_str", "")
        new_str = tool_input.get("new_str", "")
        return _handle_str_replace_command(db, path, old_str, new_str)

    elif command == "insert":
        path = tool_input.get("path", "")
        insert_line = tool_input.get("insert_line", 0)
        new_str = tool_input.get("new_str", "")
        return _handle_insert_command(db, path, insert_line, new_str)

    elif command == "create":
        return "Error: The create command is disabled. All opinions already exist in the database."

    else:
        return f"Error: Unknown command '{command}'"


async def run_interactive_agent(
    db: Session,
    client: AsyncAnthropic,
    model: str,
) -> None:
    """
    Run an interactive editing agent loop.

    Prompts the user for input, sends to Claude, displays response,
    and repeats until the user exits.

    Args:
        db: Database session
        client: Anthropic async client
        model: Claude model to use
    """
    messages = []

    # Create prompt session with history
    session = PromptSession(history=InMemoryHistory())

    CONSOLE.print("\n[bold cyan]Fantasy Court Opinion Editor[/bold cyan]")
    CONSOLE.print(
        "[dim]Multiline editing enabled. Press [Meta+Enter] or [Esc Enter] to submit.[/dim]"
    )
    CONSOLE.print(
        "[dim]Commands: 'exit' to quit, '/clear' to reset conversation.[/dim]"
    )
    CONSOLE.print(
        "[dim]You can ask the agent to list opinions, view files, and make edits.[/dim]\n"
    )

    while True:
        # Get user input with prompt_toolkit (supports editing, history, multiline)
        try:
            user_input = await session.prompt_async(
                "You: ",
                multiline=True,
            )
            user_input = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            CONSOLE.print("\n[bold cyan]Goodbye![/bold cyan]\n")
            break

        if not user_input:
            continue

        # Check for exit commands
        if user_input.lower() in ["exit", "quit", "q"]:
            CONSOLE.print("\n[bold cyan]Goodbye![/bold cyan]\n")
            break

        # Check for /clear command
        if user_input == "/clear":
            messages = []
            CONSOLE.print("[yellow]Conversation cleared.[/yellow]\n")
            continue

        # Show that message was sent
        CONSOLE.print("[dim]" + "─" * 80 + "[/dim]")

        # Add user message to history
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        # Agent loop: keep calling API until no more tool uses
        while True:
            # Make API call with interleaved thinking and stream output
            async with client.beta.messages.stream(
                model=model,
                max_tokens=16000,
                thinking={"type": "enabled", "budget_tokens": 10000},
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=[
                    {
                        "type": "text_editor_20250728",
                        "name": "str_replace_based_edit_tool",
                    }
                ],
                betas=["interleaved-thinking-2025-05-14"],
                messages=messages,
            ) as stream:
                # Track current content block being streamed
                current_block_type = None
                current_block_text = []

                async for event in stream:
                    if event.type == "content_block_start":
                        # New content block starting
                        current_block_type = event.content_block.type
                        current_block_text = []

                        if current_block_type == "thinking":
                            CONSOLE.print("\n[yellow]thinking:[/yellow] ", end="")
                        elif current_block_type == "text":
                            CONSOLE.print("\n[cyan]assistant:[/cyan] ", end="")
                        elif current_block_type == "tool_use":
                            tool_name = event.content_block.name
                            CONSOLE.print(
                                f"\n[green]tool:[/green] {tool_name} ", end=""
                            )

                    elif event.type == "content_block_delta":
                        # Incremental content for current block
                        delta = event.delta

                        if hasattr(delta, "thinking") and delta.thinking:
                            # Streaming thinking text
                            CONSOLE.print(
                                f"[dim yellow]{delta.thinking}[/dim yellow]", end=""
                            )
                            current_block_text.append(delta.thinking)

                        elif hasattr(delta, "text") and delta.text:
                            # Streaming assistant text
                            CONSOLE.print(delta.text, end="")
                            current_block_text.append(delta.text)

                        elif hasattr(delta, "partial_json") and delta.partial_json:
                            # Tool use arguments being built (just show we're receiving it)
                            pass

                    elif event.type == "content_block_stop":
                        # Content block finished
                        if current_block_type in ["thinking", "text"]:
                            CONSOLE.print()  # New line after block
                        elif current_block_type == "tool_use":
                            CONSOLE.print()

                        current_block_type = None
                        current_block_text = []

            response = await stream.get_final_message()

            # Extract tool use blocks (we already displayed thinking/text while streaming)
            tool_use_blocks = [
                block for block in response.content if block.type == "tool_use"
            ]

            # Add assistant message to history
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                }
            )

            # If there are tool uses, process them
            if tool_use_blocks:
                tool_results = []

                for tool_use in tool_use_blocks:
                    # Format the tool arguments nicely
                    args_str = ", ".join(
                        f"{k}={repr(v)[:100]}" for k, v in tool_use.input.items()
                    )
                    CONSOLE.print(f"[dim]  Called with: {args_str}[/dim]")

                    # Process the tool use
                    result = _process_tool_use(db, tool_use.input)

                    # Show the result (abbreviated if long)
                    if len(result) > 500:
                        result_preview = (
                            result[:500] + f"... ({len(result)} chars total)"
                        )
                    else:
                        result_preview = result
                    CONSOLE.print(f"[dim]→ {result_preview}[/dim]\n")

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result,
                        }
                    )

                # Remove previous cache controls to avoid exceeding the 4-block limit
                _remove_cache_controls(messages)

                # Add cache control to last tool result (often large opinion bodies)
                if tool_results:
                    tool_results[-1]["cache_control"] = {"type": "ephemeral"}

                # Add tool results to messages
                messages.append(
                    {
                        "role": "user",
                        "content": tool_results,
                    }
                )

                # Continue loop to get next response
                continue
            else:
                # No tool uses, break out of agent loop
                break

        # Show that agent is done
        CONSOLE.print("[dim]" + "─" * 80 + "[/dim]\n")


@click.command()
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_MODEL,
    help="Claude model to use for editing",
)
def main(model: str):
    """Interactive Fantasy Court opinion editor."""
    console = Console()

    console.print(
        f"\n[bold blue]Starting Opinion Editor with model:[/bold blue] {model}\n"
    )

    db = get_session()
    client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_API_KEY)

    asyncio.run(run_interactive_agent(db, client, model))


if __name__ == "__main__":
    main()
