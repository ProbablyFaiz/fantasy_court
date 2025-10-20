"""CLI commands for Fantasy Court inference operations."""

import asyncio

import anthropic
import openai
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlalchemy.orm import Session, selectinload

from court.db.models import (
    EpisodeTranscript,
    FantasyCourtCase,
    FantasyCourtOpinion,
    FantasyCourtSegment,
    PodcastEpisode,
)
from court.db.session import get_session
from court.inference import create_cases as create_cases_module
from court.inference import create_citations as create_citations_module
from court.inference import create_opinions as create_opinions_module
from court.inference import create_segments as create_segments_module
from court.inference import editor_agent
from court.inference.create_cases import (
    _DEFAULT_MODEL as _DEFAULT_CLAUDE_MODEL,
)
from court.inference.create_cases import (
    extract_fantasy_court_cases,
)
from court.inference.create_opinions import run_opinion_drafting_agent
from court.inference.create_segments import (
    _DEFAULT_MODEL as _DEFAULT_OPENAI_MODEL,
)
from court.inference.create_segments import (
    detect_fantasy_court_segment,
    seconds_to_timestamp,
)
from court.inference.utils import get_or_create_provenance, should_save_prompt
from court.utils.print import CONSOLE


@click.group()
def inference():
    """Fantasy Court inference utilities."""
    rl.utils.io.ensure_dotenv_loaded()


@inference.command()
@click.option(
    "--episode-id",
    "-e",
    type=int,
    required=True,
    help="ID of the podcast episode to analyze",
)
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_OPENAI_MODEL,
    help="OpenAI model to use for segment detection",
)
@click.option(
    "--save",
    type=click.Choice(["yes", "ask", "no"], case_sensitive=False),
    default="ask",
    help="Whether to save detected segment to database",
)
def detect_segment(episode_id: int, model: str, save: str):
    """Detect Fantasy Court segment in a specific episode using GPT-5-mini.

    This command analyzes a single episode to determine if it contains a Fantasy Court
    segment and extracts the start/end timestamps if found. The segment can optionally
    be saved to the database.
    """
    session: Session = get_session()

    # Load the episode
    episode = session.execute(
        sa.select(PodcastEpisode).where(PodcastEpisode.id == episode_id)
    ).scalar_one_or_none()

    if not episode:
        raise click.ClickException(f"Episode with ID {episode_id} not found")

    # Display episode info
    CONSOLE.print("\n[bold blue]Analyzing Episode:[/bold blue]")
    CONSOLE.print(f"  [cyan]ID:[/cyan] {episode.id}")
    CONSOLE.print(f"  [cyan]Title:[/cyan] {episode.title}")
    CONSOLE.print(f"  [cyan]Published:[/cyan] {episode.pub_date.strftime('%B %d, %Y')}")
    if episode.duration_seconds:
        CONSOLE.print(
            f"  [cyan]Duration:[/cyan] {seconds_to_timestamp(episode.duration_seconds)}"
        )
    CONSOLE.print(f"  [cyan]Model:[/cyan] {model}\n")

    # Create OpenAI client and detect segment
    client = openai.AsyncOpenAI()

    async def run_detection():
        return await detect_fantasy_court_segment(client, episode, model)

    segment = asyncio.run(run_detection())

    # Display results
    if segment is None:
        CONSOLE.print(
            "[bold yellow]No Fantasy Court segment detected in this episode[/bold yellow]\n"
        )
    else:
        CONSOLE.print("[bold green]Fantasy Court segment detected![/bold green]\n")

        duration = segment.end_time_s - segment.start_time_s
        CONSOLE.print(
            f"  [cyan]Start Time:[/cyan] {seconds_to_timestamp(segment.start_time_s)}"
        )
        CONSOLE.print(
            f"  [cyan]End Time:[/cyan] {seconds_to_timestamp(segment.end_time_s)}"
        )
        CONSOLE.print(f"  [cyan]Duration:[/cyan] {seconds_to_timestamp(duration)}")

        # Handle saving to database
        if should_save_prompt(save, "Save this segment to the database?"):
            # Check for existing segment for this episode
            existing_segment = session.execute(
                sa.select(FantasyCourtSegment).where(
                    FantasyCourtSegment.episode_id == episode_id
                )
            ).scalar_one_or_none()

            if existing_segment:
                CONSOLE.print(
                    "\n[yellow]Found existing segment for this episode.[/yellow]"
                )
                CONSOLE.print(
                    f"  - Segment ID {existing_segment.id}: {seconds_to_timestamp(existing_segment.start_time_s)} - {seconds_to_timestamp(existing_segment.end_time_s)}"
                )
                CONSOLE.print(
                    "[yellow]This will be deleted to avoid duplicates.[/yellow]\n"
                )
                session.delete(existing_segment)
                session.flush()

            # Get or create provenance record
            provenance = get_or_create_provenance(
                session,
                task_name="detect_segment",
                creator_name=model,
                record_type="fantasy_court_segments",
            )

            # Assign provenance and save
            segment.provenance_id = provenance.id
            session.add(segment)
            session.commit()

            CONSOLE.print("\n[bold green]Saved segment to database![/bold green]\n")
        else:
            CONSOLE.print(
                "\n[dim]Note: This segment has not been saved to the database.[/dim]"
            )
            CONSOLE.print(
                "[dim]To create segments for all episodes, run: [blue]court inference create-segments[/blue][/dim]\n"
            )


@inference.command()
@click.option(
    "--transcript-id",
    "-t",
    type=int,
    required=True,
    help="ID of the transcript to print",
)
def print_transcript(transcript_id: int):
    """Display a transcript in a rich, formatted view.

    This command prints a transcript with episode information and speaker utterances
    in a visually appealing format using timestamps and speaker labels.
    """
    session: Session = get_session()

    # Load the transcript with episode relationship
    transcript = session.execute(
        sa.select(EpisodeTranscript)
        .where(EpisodeTranscript.id == transcript_id)
        .options(selectinload(EpisodeTranscript.episode))
    ).scalar_one_or_none()

    if not transcript:
        raise click.ClickException(f"Transcript with ID {transcript_id} not found")

    episode = transcript.episode

    # Display episode info in a panel
    episode_info = Table.grid(padding=(0, 2))
    episode_info.add_column(style="cyan", justify="right")
    episode_info.add_column()

    episode_info.add_row("Episode ID:", str(episode.id))
    episode_info.add_row("Title:", episode.title)
    episode_info.add_row("Published:", episode.pub_date.strftime("%B %d, %Y"))
    if episode.duration_seconds:
        episode_info.add_row(
            "Duration:", seconds_to_timestamp(episode.duration_seconds)
        )
    episode_info.add_row(
        "Transcript Start:", seconds_to_timestamp(transcript.start_time_s)
    )
    episode_info.add_row("Transcript End:", seconds_to_timestamp(transcript.end_time_s))
    duration = transcript.end_time_s - transcript.start_time_s
    episode_info.add_row("Transcript Duration:", seconds_to_timestamp(duration))

    CONSOLE.print(
        Panel(
            episode_info,
            title="[bold blue]Episode Information[/bold blue]",
            border_style="blue",
        )
    )
    CONSOLE.print()

    # Parse transcript and get utterances
    transcript_obj = transcript.transcript_obj()
    utterances = transcript_obj.get_utterances()

    # Display utterances
    CONSOLE.print(
        f"[bold green]Transcript ({len(utterances)} utterances)[/bold green]\n"
    )

    # Speaker colors for consistent styling
    speaker_colors = {}
    color_options = ["magenta", "yellow", "cyan", "green", "blue", "red"]

    for utterance in utterances:
        # Assign a color to each unique speaker
        if utterance.speaker not in speaker_colors:
            color_idx = len(speaker_colors) % len(color_options)
            speaker_colors[utterance.speaker] = color_options[color_idx]

        speaker_color = speaker_colors[utterance.speaker]

        # Format timestamp
        timestamp = Text(
            f"[{seconds_to_timestamp(utterance.start)} - {seconds_to_timestamp(utterance.end)}]",
            style="dim",
        )

        # Format speaker
        speaker = Text(f"{utterance.speaker}:", style=f"bold {speaker_color}")

        # Combine and print
        CONSOLE.print(timestamp, end=" ")
        CONSOLE.print(speaker, end=" ")
        CONSOLE.print(utterance.text)
        CONSOLE.print()

    CONSOLE.print(f"[dim]Total utterances: {len(utterances)}[/dim]\n")


@inference.command()
@click.option(
    "--segment-id",
    "-s",
    type=int,
    required=True,
    help="ID of the Fantasy Court segment to extract cases from",
)
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_CLAUDE_MODEL,
    help="Claude model to use for case extraction",
)
@click.option(
    "--save",
    type=click.Choice(["yes", "ask", "no"], case_sensitive=False),
    default="ask",
    help="Whether to save extracted cases to database",
)
def extract_cases(segment_id: int, model: str, save: str):
    """Extract Fantasy Court cases from a segment using Claude.

    This command analyzes a Fantasy Court segment's transcript and extracts
    individual cases with formal legal information. Cases are displayed and
    can optionally be saved to the database.
    """
    session: Session = get_session()

    # Load the segment with all required relationships
    segment = session.execute(
        sa.select(FantasyCourtSegment)
        .where(FantasyCourtSegment.id == segment_id)
        .options(
            selectinload(FantasyCourtSegment.episode),
            selectinload(FantasyCourtSegment.transcript),
        )
    ).scalar_one_or_none()

    if not segment:
        raise click.ClickException(f"Segment with ID {segment_id} not found")

    if not segment.transcript:
        raise click.ClickException(f"Segment {segment_id} has no transcript available")

    episode = segment.episode

    # Display segment info
    CONSOLE.print("\n[bold blue]Extracting cases from segment:[/bold blue]")
    CONSOLE.print(f"  [cyan]Segment ID:[/cyan] {segment.id}")
    CONSOLE.print(f"  [cyan]Episode:[/cyan] {episode.title}")
    CONSOLE.print(f"  [cyan]Published:[/cyan] {episode.pub_date.strftime('%B %d, %Y')}")
    CONSOLE.print(
        f"  [cyan]Segment:[/cyan] {seconds_to_timestamp(segment.start_time_s)} - {seconds_to_timestamp(segment.end_time_s)}"
    )
    CONSOLE.print(f"  [cyan]Model:[/cyan] {model}\n")

    # Create Anthropic client and extract cases
    client = anthropic.AsyncAnthropic()

    async def run_extraction():
        return await extract_fantasy_court_cases(segment, client, model)

    cases = asyncio.run(run_extraction())

    # Display results
    if not cases:
        CONSOLE.print(
            "[bold yellow]No cases extracted from this segment[/bold yellow]\n"
        )
    else:
        CONSOLE.print(f"[bold green]Extracted {len(cases)} case(s)![/bold green]\n")

        for i, case in enumerate(cases, 1):
            # Create panel for each case
            case_info = []

            # Header
            case_info.append(
                f"[bold white]{case.case_caption or '(no caption)'}[/bold white]\n"
            )

            # Timestamps
            duration = case.end_time_s - case.start_time_s
            case_info.append(
                f"[cyan]Time:[/cyan] {seconds_to_timestamp(case.start_time_s)} - {seconds_to_timestamp(case.end_time_s)}"
            )
            case_info.append(
                f"[cyan]Duration:[/cyan] {seconds_to_timestamp(duration)}\n"
            )

            # Procedural posture
            case_info.append(
                f"[yellow]Procedural Posture:[/yellow] {case.procedural_posture or 'N/A'}\n"
            )

            # Questions presented
            case_info.append(
                f"[yellow]Questions Presented:[/yellow]\n{case.questions_presented_html or 'N/A'}\n"
            )

            # Fact summary
            case_info.append(f"[yellow]Facts:[/yellow]\n{case.fact_summary}\n")

            # Topics
            topics_str = ", ".join(case.case_topics) if case.case_topics else "N/A"
            case_info.append(f"[magenta]Topics:[/magenta] {topics_str}")

            CONSOLE.print(
                Panel(
                    "\n".join(case_info),
                    title=f"[bold]Case {i}[/bold]",
                    border_style="green",
                )
            )
            CONSOLE.print()

        # Handle saving to database
        if should_save_prompt(save, "Save these cases to the database?"):
            # Check for existing cases for this segment
            existing_cases = (
                session.execute(
                    sa.select(FantasyCourtCase).where(
                        FantasyCourtCase.segment_id == segment_id
                    )
                )
                .scalars()
                .all()
            )

            if existing_cases:
                CONSOLE.print(
                    f"\n[yellow]Found {len(existing_cases)} existing case(s) for this segment.[/yellow]"
                )
                for existing_case in existing_cases:
                    CONSOLE.print(
                        f"  - {existing_case.docket_number}: {existing_case.case_caption or '(no caption)'}"
                    )
                CONSOLE.print(
                    "[yellow]These will be deleted to avoid duplicates.[/yellow]\n"
                )
                for existing_case in existing_cases:
                    session.delete(existing_case)
                session.flush()

            # Get or create provenance record
            provenance = get_or_create_provenance(
                session,
                task_name="extract_cases",
                creator_name=model,
                record_type="fantasy_court_cases",
            )

            # Assign provenance to all cases
            for case in cases:
                case.provenance_id = provenance.id

            # Save to database
            session.add_all(cases)
            session.commit()

            CONSOLE.print(
                f"\n[bold green]Saved {len(cases)} case(s) to database![/bold green]\n"
            )
        else:
            CONSOLE.print(
                "\n[dim]Note: These cases have not been saved to the database.[/dim]"
            )
            CONSOLE.print(
                "[dim]To create cases for all segments, run: [blue]court inference create-cases[/blue][/dim]\n"
            )


@inference.command()
@click.option(
    "--case-id",
    "-c",
    type=int,
    required=True,
    help="ID of the Fantasy Court case to draft opinion for",
)
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_CLAUDE_MODEL,
    help="Claude model to use for opinion drafting",
)
@click.option(
    "--save",
    type=click.Choice(["yes", "ask", "no"], case_sensitive=False),
    default="ask",
    help="Whether to save drafted opinion to database",
)
def draft_opinion(case_id: int, model: str, save: str):
    """Draft a Fantasy Court opinion for a specific case using Claude.

    This command runs an AI agent that analyzes the case transcript, reviews
    past opinions for precedent, and drafts a complete legal opinion with all
    required fields. The opinion can optionally be saved to the database.
    """
    session: Session = get_session()

    # Load the case with all required relationships
    case = session.execute(
        sa.select(FantasyCourtCase)
        .where(FantasyCourtCase.id == case_id)
        .options(
            selectinload(FantasyCourtCase.episode),
            selectinload(FantasyCourtCase.segment).selectinload(
                FantasyCourtSegment.transcript
            ),
        )
    ).scalar_one_or_none()

    if not case:
        raise click.ClickException(f"Case with ID {case_id} not found")

    if not case.segment:
        raise click.ClickException(f"Case {case_id} has no associated segment")

    if not case.segment.transcript:
        raise click.ClickException(
            f"Case {case_id}'s segment has no transcript available"
        )

    episode = case.episode

    # Display case info
    CONSOLE.print("\n[bold blue]Drafting opinion for case:[/bold blue]")
    CONSOLE.print(f"  [cyan]Case ID:[/cyan] {case.id}")
    CONSOLE.print(f"  [cyan]Docket Number:[/cyan] {case.docket_number}")
    CONSOLE.print(
        f"  [cyan]Caption:[/cyan] {case.case_caption or '(no caption provided)'}"
    )
    CONSOLE.print(f"  [cyan]Episode:[/cyan] {episode.title}")
    CONSOLE.print(f"  [cyan]Published:[/cyan] {episode.pub_date.strftime('%B %d, %Y')}")
    CONSOLE.print(
        f"  [cyan]Case Time:[/cyan] {seconds_to_timestamp(case.start_time_s)} - {seconds_to_timestamp(case.end_time_s)}"
    )
    if case.case_topics:
        CONSOLE.print(f"  [cyan]Topics:[/cyan] {', '.join(case.case_topics)}")
    CONSOLE.print(f"  [cyan]Model:[/cyan] {model}\n")

    # Create Anthropic client and draft opinion
    client = anthropic.AsyncAnthropic()

    CONSOLE.print("[bold yellow]Starting opinion drafting agent...[/bold yellow]")
    CONSOLE.print(
        "[dim]The agent will analyze the transcript, review precedent, and draft the opinion.[/dim]"
    )
    CONSOLE.print("[dim]Progress will be shown below as the agent works...[/dim]\n")

    opinion = asyncio.run(run_opinion_drafting_agent(session, client, model, case))

    # Display results
    CONSOLE.print("[bold blue]Displaying drafted opinion:[/bold blue]\n")

    # Create panels for each part of the opinion
    CONSOLE.print(
        Panel(
            opinion.authorship_html,
            title="[bold]Authorship[/bold]",
            border_style="blue",
        )
    )
    CONSOLE.print()

    CONSOLE.print(
        Panel(
            opinion.holding_statement_html,
            title="[bold]Holding[/bold]",
            border_style="green",
        )
    )
    CONSOLE.print()

    CONSOLE.print(
        Panel(
            opinion.reasoning_summary_html,
            title="[bold]Reasoning Summary[/bold]",
            border_style="yellow",
        )
    )
    CONSOLE.print()

    # For the opinion body, show a preview
    body_lines = opinion.opinion_body_html.split("\n")
    body_preview = "\n".join(body_lines[:20])
    if len(body_lines) > 20:
        body_preview += f"\n\n[dim]... ({len(body_lines) - 20} more lines)[/dim]"

    CONSOLE.print(
        Panel(
            body_preview,
            title="[bold]Opinion Body (Preview)[/bold]",
            border_style="magenta",
        )
    )
    CONSOLE.print()

    # Handle saving to database
    if should_save_prompt(save, "Save this opinion to the database?"):
        # Check for existing opinion for this case
        existing_opinion = session.execute(
            sa.select(FantasyCourtOpinion).where(FantasyCourtOpinion.case_id == case_id)
        ).scalar_one_or_none()

        if existing_opinion:
            CONSOLE.print(
                f"\n[yellow]Found existing opinion for this case (Opinion ID {existing_opinion.id}).[/yellow]"
            )
            CONSOLE.print(
                "[yellow]This will be deleted to avoid duplicates.[/yellow]\n"
            )
            session.delete(existing_opinion)
            session.flush()

        # Get or create provenance record
        provenance = get_or_create_provenance(
            session,
            task_name="draft_opinion",
            creator_name=model,
            record_type="fantasy_court_opinions",
        )

        # Assign provenance and save
        opinion.provenance_id = provenance.id
        session.add(opinion)
        session.commit()

        CONSOLE.print("\n[bold green]Saved opinion to database![/bold green]")
        CONSOLE.print(f"[cyan]Opinion ID:[/cyan] {opinion.id}\n")
    else:
        CONSOLE.print(
            "\n[dim]Note: This opinion has not been saved to the database.[/dim]"
        )
        CONSOLE.print(
            "[dim]To draft opinions for all cases, run: [blue]court inference create-opinions[/blue][/dim]\n"
        )


# Register batch processing commands from their respective modules
inference.add_command(create_segments_module.main, name="create-segments")
inference.add_command(create_cases_module.main, name="create-cases")
inference.add_command(create_opinions_module.main, name="create-opinions")

inference.add_command(create_citations_module.main, name="create-citations")

# Register interactive editor agent
inference.add_command(editor_agent.main, name="edit-opinion")
