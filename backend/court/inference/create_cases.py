"""Extract Fantasy Court cases from segment transcripts using Claude."""

import asyncio

import anthropic
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
from pydantic import BaseModel, Field
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session, selectinload

from court.db.models import (
    FantasyCourtCase,
    FantasyCourtSegment,
    PodcastEpisode,
)
from court.db.session import get_session
from court.inference.utils import get_or_create_provenance

_ANTHROPIC_API_KEY = rl.utils.io.getenv("ANTHROPIC_API_KEY")

_DEFAULT_MODEL = "claude-opus-4-5-20251101"
_DEFAULT_CONCURRENCY = 8
_CREATOR_NAME = "claude-opus-4-5-20251101"
_TASK_NAME = "create_cases"
_RECORD_TYPE = "fantasy_court_cases"

# System prompt for case extraction with detailed instructions
_SYSTEM_PROMPT = """You are a judicial clerk for the Fantasy Court, a tribunal that adjudicates fantasy football disputes on "The Ringer Fantasy Football Show" podcast.

The hosts, err, justices, are Chief Justice Danny Heifetz, Justice Danny Kelly, and Justice Craig Horlbeck.

Your role is to extract and formalize case information from Fantasy Court segment transcripts. Each Fantasy Court segment may contain one or more distinct cases - each representing a different listener's dispute or controversy.

## Your Task

For each distinct case in the transcript, you must extract the following information with appropriate legal formality, dry wit, and creativity:

### 1. CASE CAPTION (Optional but encouraged)
A concise, formal case title that captures the essence of the dispute. Follow these patterns:

**Examples:**
- "Alec v. Nick" (adversarial disputes between league members)
- "In re Roster Management During Wife's Labor" (petition-style for individual controversies or where party names are unclear)
- "People v. Taysom Hill" (criminal-style for egregious global-scale fantasy football offenses or Fantasy Supreme Court)

If a petitioner (e.g. named James) seeks relief from their league and is denied, and is effectively appealing the decision, we can think of it as an appeal from the league or Commissioner's administrative decision, such that the case caption would be "James v. League", or, if funnier, "James v. Commissioner". IMPORTANT: Prefer this adversarial style of caption whenever a petitioner's name is present over the "In re" descriptive style. However, in the labor example given below, because the petitioner is seeking an advisory opinion about an action he may take, the "In re" descriptive style is preferable since there isn't an active controversy between multiple parties.

Do not include parentheticals in the case caption.

**Guidelines:** Be creative but authentic to legal caption conventions. Capture the absurdity while maintaining gravitas.

### 2. FACT SUMMARY
A comprehensive but concise summary of the underlying facts giving rise to the dispute. Write in formal legal prose, third person past tense.

**Style notes:**
- Use precise, formal language ("Petitioner contends," "Respondent maintains," "The Commissioner ruled")
- Include relevant dates, player names, scoring details, and league context
- Maintain deadpan seriousness about inherently ridiculous situations
- Length: 2-5 sentences typically

**Example:**
"Petitioner's spouse entered labor during the 1:00 PM slate of games. Petitioner faced a decision whether to make crucial roster substitutions or attend the birth. Petitioner eventually departed for the hospital, leaving two injured players in his starting lineup. Petitioner now seeks retroactive roster adjustments, arguing that the extraordinary circumstances constitute force majeure."

### 3. QUESTIONS PRESENTED (Optional but encouraged, HTML format)
The legal question(s) before the Court, formatted in HTML with proper styling. Use italics for Latin phrases and case references as appropriate.

**CRITICAL:** The Questions Presented must reflect what the petitioner/disputant actually asked or the core dispute they raised. Do NOT invent additional legal questions beyond what was actually presented. Most cases will have only ONE question presented.

**Format:** Questions should be framed formally and specifically. For multiple questions (rare), use an ordered list.

**How to identify the question(s):**
- Look for what the emailer explicitly asks: "Is this allowed?" "Can I do X?" "Should the commissioner have ruled differently?"
- Focus on the core dispute, not tangential issues
- Distinguish between the question presented vs. interesting factual details (which belong in the opinion, not the QP)

**Examples:**
- Simple dispute: "Whether a trade negotiated while one party was demonstrably intoxicated is voidable for lack of capacity under prevailing fantasy football contract law?"
- Blackmail case where petitioner asks "is blackmail legal in the eyes of fantasy court?": "Whether blackmail—specifically, threatening to disclose a league member's roster management during his wife's active labor to his spouse in exchange for favorable trade consideration—constitutes permissible fantasy football gamesmanship or violates fundamental principles of fair dealing?"
- Multiple questions example (use sparingly - only when petitioner truly raises multiple distinct questions):
  "
  <ol>
    <li>Whether the Commissioner's familial relationship with the trade partner constitutes a disqualifying conflict of interest requiring recusal from trade approval authority?</li>
    <li>If so, whether the trade approved by the conflicted Commissioner is voidable <em>ab initio</em>, or whether the complaining party must demonstrate actual prejudice resulting from the conflict?</li>
  </ol>"

**What NOT to include as Questions Presented:**
- Issues the hosts raise but the petitioner didn't ask about
- Tangential factual developments (e.g., if petitioner asks about blackmail, don't add separate questions about whether telling his wife was wrong)
- Potential sanctions or remedies not requested by the petitioner

### 4. PROCEDURAL POSTURE (Optional but encouraged)
How the case arrived at Fantasy Court - the procedural history in formal legal terminology.

**Examples:**
- "Original petition for extraordinary relief"
- "Appeal from the Commissioner's denial of protest"
- "Interlocutory appeal from League Rules Committee ruling"
- "Petition for writ of mandamus to compel Commissioner action"
- "Motion to vacate trade on grounds of fraud and undue influence"
- "Complaint seeking declaratory and injunctive relief"

### 5. CASE TOPICS (Optional, list of strings)
Categorical tags for the legal issues involved. Use formal but specific categories.

**Common topics:**
- "corrupt dealing"
- "scoring dispute"
- "retroactive substitution"
- "waiver wire irregularities"
- "trade fairness"
- "commissioner misconduct"
- "rules interpretation"
- "collusion"
- "blackmail"
- "force majeure"
- "constitutional challenge"
- "conflicts of interest"
- "emergency relief"
- "procedural irregularities"

Be creative with topics - invent new precise categories as needed while maintaining legal formality.

### 6. TIMESTAMPS
Provide the approximate start and end time (in seconds, relative to the episode start) for discussion of this particular case. If multiple cases exist in a segment, ensure they don't overlap significantly.

## Important Guidelines

1. **Maintain Faux-Realism:** The tone should be deadly serious and formally legal, which creates the humor when applied to fantasy football disputes. Think Supreme Court opinion meets fantasy football absurdity.

2. **Use Modern Legal Language:** Imitate contemporary federal courts (Supreme Court, Circuit Courts) circa 2025, not archaic 1800s English common law. Avoid overly technical or antiquated terms like "parturient" when "spouse" or "wife giving birth" would be clear and natural. Latin phrases used in modern practice (e.g., force majeure) are fine.

3. **Be Specific:** Include specific details from the transcript - player names, scores, dates, league context. Precision enhances both the legal gravitas and the comedy.

4. **Ground Analysis in Transcript:** Review what the petitioner actually asks or disputes. For example:
   - If transcript shows: "is blackmail legal in the eyes of fantasy court?" → Your QP should focus on the legality of blackmail
   - If transcript shows: "can I get retroactive substitution for being in the ER?" → Your QP should focus on whether medical emergency justifies retroactive relief
   - Don't add questions about issues raised only in the hosts' discussion/commentary

5. **Creativity within Constraints:** You have latitude to formalize and stylize the language, but remain faithful to the actual facts discussed in the podcast. Don't make up facts that are not discussed in the transcript, or cannot be reasonably inferred from the transcript.

6. **Multiple Cases:** If the segment discusses multiple distinct listener disputes, extract each as a separate case. If it's one continuous discussion of a single dispute, that's one case.

7. **Maintain Accessibility:** Use formal legal language and structure, but avoid excessive jargon or overly complex legal constructions that would confuse a typical fantasy football podcast listener. The goal is legally authentic and funny, not impenetrable. Think Neil Gorsuch or Elena Kagan in 2025, not John Marshall in the 1800s.

**Example - Compare these fact summary styles:**

TOO STIFF (avoid this):
"Petitioner's sister entered labor for the delivery of her second child. Petitioner and his spouse assumed childcare duties for the couple's first child during the hospitalization. At 4:23 PM, Petitioner observed through the fantasy application that his brother-in-law (the expectant father) had executed multiple roster transactions, including defensive and wide receiver substitutions. The child was born at 4:30 PM—a mere seven to twelve minutes after said roster moves were completed."

BETTER (aim for this):
"Petitioner's sister went into labor with her second child. Petitioner and his wife watched their first child while the couple was at the hospital. At 4:23 PM, Petitioner noticed that his brother-in-law had made several roster moves on the fantasy app, adding a new defense and a wide receiver. It later became clear that the baby was born at 4:30 PM—seven to twelve minutes after the roster transactions. When Petitioner mentioned this timeline to his wife, she became immediately furious. Petitioner seeks a ruling on whether he may use this information to extract favorable trade consideration from his brother-in-law in exchange for his silence."

8. **HTML in Questions:** Use HTML formatting in questions_presented_html:
   - `<em>` for emphasis, case names, and Latin phrases
   - Standard HTML tags as appropriate

Your extractions will be used to generate official-looking case documents, so maintain appropriate legal register throughout.

Do not include a 'parameter' or 'parameters' parent key in your tool use output; return the JSON directly with the 'cases' key
in the top level.
"""


class CaseExtraction(BaseModel):
    """Structured output for a single Fantasy Court case extraction."""

    start_time_s: float = Field(
        description="Start time in seconds (relative to episode start, not segment start)"
    )
    end_time_s: float = Field(
        description="End time in seconds (relative to episode start, not segment start)"
    )
    fact_summary: str = Field(
        description="Formal summary of the facts giving rise to the dispute"
    )
    case_caption: str | None = Field(
        default=None,
        description='Optional formal case title, e.g. "Alec v. Nick" or "In re Roster Management"',
    )
    questions_presented_html: str | None = Field(
        default=None,
        description="The legal question(s) before the court, formatted as HTML",
    )
    procedural_posture: str | None = Field(
        default=None,
        description='How the case arrived at court, e.g. "Appeal from Commissioner\'s ruling"',
    )
    case_topics: list[str] | None = Field(
        default=None,
        description='Categorical tags, e.g. ["trade fairness", "conflicts of interest"]',
    )


class CaseExtractionResponse(BaseModel):
    """Container for all cases extracted from a segment."""

    cases: list[CaseExtraction] = Field(
        description="List of distinct cases found in this Fantasy Court segment"
    )


async def extract_fantasy_court_cases(
    segment: FantasyCourtSegment,
    client: anthropic.AsyncAnthropic,
    model: str,
) -> list[FantasyCourtCase]:
    """
    Extract Fantasy Court cases from a segment transcript using Claude.

    Args:
        segment: FantasyCourtSegment with transcript and episode relationships loaded
        client: Anthropic async client
        model: Claude model to use

    Returns:
        List of FantasyCourtCase objects with docket numbers assigned (without provenance_id set, not saved to DB)
    """
    # Get the transcript - it should be eager-loaded by caller
    if not segment.transcript:
        raise ValueError(f"Segment {segment.id} has no transcript available")

    transcript = segment.transcript.transcript_obj()
    episode = segment.episode

    # Format episode context
    episode_context = f"""Episode: {episode.title}
Published: {episode.pub_date.strftime("%B %d, %Y")}
Episode ID: {episode.id}
"""

    if episode.duration_seconds:
        episode_context += f"Episode Duration: {episode.duration_seconds}s\n"

    episode_context += f"""
Fantasy Court Segment:
  Start: {segment.start_time_s:.1f}s
  End: {segment.end_time_s:.1f}s
"""

    # Format transcript with timestamps
    transcript_text = transcript.to_string(include_timestamps=True)

    # Construct user message
    user_message = f"""{episode_context}

Transcript:
{transcript_text}

Please extract all distinct Fantasy Court cases from this segment. Remember that timestamps should be relative to the episode start (not segment start), so they should fall between {segment.start_time_s:.1f}s and {segment.end_time_s:.1f}s."""

    # Call Claude with structured outputs
    response = await client.messages.create(
        model=model,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        thinking={"type": "enabled", "budget_tokens": 4096},
        messages=[{"role": "user", "content": user_message}],
        tools=[
            {
                "name": "extract_cases",
                "description": "Extract all Fantasy Court cases from the segment",
                "input_schema": CaseExtractionResponse.model_json_schema(),
            }
        ],
    )

    # Parse the response
    tool_use = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if not tool_use:
        raise ValueError("No tool use found in Claude response")

    if "parameter" in tool_use.input:
        extraction = CaseExtractionResponse.model_validate(tool_use.input["parameter"])
    else:
        extraction = CaseExtractionResponse.model_validate(tool_use.input)

    # Convert to FantasyCourtCase objects and assign docket numbers
    cases = []
    for i, case_data in enumerate(extraction.cases, start=1):
        docket_number = generate_docket_number(episode, i)
        case = FantasyCourtCase(
            episode_id=segment.episode_id,
            segment_id=segment.id,
            docket_number=docket_number,
            start_time_s=case_data.start_time_s,
            end_time_s=case_data.end_time_s,
            fact_summary=case_data.fact_summary,
            case_caption=case_data.case_caption,
            questions_presented_html=case_data.questions_presented_html,
            procedural_posture=case_data.procedural_posture,
            case_topics=case_data.case_topics,
            # Note: provenance_id will be set by caller
        )
        cases.append(case)

    return cases


def generate_docket_number(episode: PodcastEpisode, case_number: int) -> str:
    """
    Generate a docket number for a case.

    Format: YY-EEEE-N
    - YY: Last two digits of the year of the episode's publication
    - EEEE: Zero-padded 4-digit episode ID
    - N: Sequential case number (1-indexed)

    Args:
        episode: PodcastEpisode the case belongs to
        case_number: 1-indexed sequential number for this case in the episode

    Returns:
        Docket number string, e.g. "25-0197-1"
    """
    year_suffix = episode.pub_date.strftime("%y")
    episode_id_padded = str(episode.id).zfill(4)
    return f"{year_suffix}-{episode_id_padded}-{case_number}"


async def process_segments_batch(
    segments: list[FantasyCourtSegment],
    db: Session,
    provenance_id: int,
    model: str,
    concurrency: int,
    commit_batch_size: int = 16,
) -> tuple[int, int]:
    """
    Process a batch of segments with async concurrency.

    Args:
        segments: List of segments to process
        db: Database session
        provenance_id: ID of provenance record
        model: Claude model to use
        concurrency: Number of parallel requests
        commit_batch_size: Number of segments to commit at once

    Returns:
        Tuple of (cases_created, segments_processed)
    """
    console = Console()
    client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_API_KEY)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(
        segment: FantasyCourtSegment,
    ) -> tuple[FantasyCourtSegment, list[FantasyCourtCase], bool]:
        """
        Process one segment.

        Returns:
            Tuple of (segment, list of cases, True if error occurred)
        """
        async with semaphore:
            try:
                cases = await extract_fantasy_court_cases(segment, client, model)

                # Assign provenance to all cases
                for case in cases:
                    case.provenance_id = provenance_id

                return segment, cases, False
            except Exception as e:
                console.print(
                    f"[red]Error processing segment {segment.id} (episode {segment.episode_id}):[/red] {e}"
                )
                return segment, [], True

    # Process all segments concurrently, committing in batches
    tasks = [process_one(seg) for seg in segments]
    total_created = 0
    pending_commits = []
    segments_no_cases = []
    failed_count = 0

    # Use tqdm to track progress
    pbar = tqdm.tqdm(total=len(segments), desc="Processing segments")
    for coro in asyncio.as_completed(tasks):
        segment, cases, had_error = await coro

        if not cases and had_error:
            failed_count += 1
        elif not cases:
            # No cases found and no error - mark segment as checked
            segments_no_cases.append(segment)
        else:
            pending_commits.extend(cases)

        # Commit when batch is full
        if len(pending_commits) >= commit_batch_size:
            db.add_all(pending_commits)
            db.commit()
            total_created += len(pending_commits)
            pending_commits = []

        pbar.update(1)
    pbar.close()

    # Commit any remaining cases and mark segments with no cases
    if pending_commits:
        db.add_all(pending_commits)

    for segment in segments_no_cases:
        segment.found_no_cases = True

    if pending_commits or segments_no_cases:
        db.commit()
        total_created += len(pending_commits)

    if failed_count > 0:
        console.print(
            f"\n[yellow]Warning:[/yellow] {failed_count} segment(s) failed to process\n"
        )

    return total_created, len(segments)


@click.command()
@click.option(
    "--model",
    "-m",
    type=str,
    default=_DEFAULT_MODEL,
    help="Claude model to use for case extraction",
)
@click.option(
    "--concurrency",
    "-c",
    type=int,
    default=_DEFAULT_CONCURRENCY,
    help="Number of parallel requests to make",
)
def main(model: str, concurrency: int):
    """Extract and create Fantasy Court case records using Claude."""
    console = Console()

    console.print(
        f"\n[bold blue]Creating Fantasy Court cases using:[/bold blue] {model}"
    )
    console.print(f"[bold blue]Concurrency:[/bold blue] {concurrency}\n")

    db = get_session()

    # Create or get provenance record
    provenance = get_or_create_provenance(
        db,
        _TASK_NAME,
        _CREATOR_NAME,
        _RECORD_TYPE,
    )
    db.commit()  # Commit to ensure provenance is persisted

    # Get segments that have transcripts but don't have cases yet and haven't been checked
    segments_query = (
        sa.select(FantasyCourtSegment)
        .join(FantasyCourtSegment.transcript)
        .outerjoin(FantasyCourtCase)
        .where(
            FantasyCourtCase.id.is_(None),
            FantasyCourtSegment.found_no_cases.is_(False),
        )
        .options(
            selectinload(FantasyCourtSegment.episode),
            selectinload(FantasyCourtSegment.transcript),
        )
        .order_by(FantasyCourtSegment.id)
    )

    segments = db.execute(segments_query).scalars().all()

    console.print(
        f"[bold]Found {len(segments)} segments with transcripts but no cases[/bold]\n"
    )

    if not segments:
        console.print("[yellow]No segments to process[/yellow]\n")
        return

    # Process segments
    cases_created, segments_processed = asyncio.run(
        process_segments_batch(segments, db, provenance.id, model, concurrency)
    )

    console.print(
        f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{cases_created}[/bold cyan] "
        f"cases from [bold]{segments_processed}[/bold] segments processed\n"
    )

    # Display a table with created cases
    if cases_created > 0:
        table = Table(
            title="Sample Created Cases (first 10)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Docket", style="cyan", width=12)
        table.add_column("Caption", style="green", max_width=40)
        table.add_column("Episode", style="magenta", max_width=30)

        # Fetch recently created cases
        recent_cases = (
            db.execute(
                sa.select(FantasyCourtCase)
                .where(FantasyCourtCase.provenance_id == provenance.id)
                .options(selectinload(FantasyCourtCase.episode))
                .order_by(FantasyCourtCase.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        for case in recent_cases:
            table.add_row(
                case.docket_number,
                case.case_caption or "(no caption)",
                case.episode.title,
            )

        console.print(table)
        console.print()


if __name__ == "__main__":
    main()
