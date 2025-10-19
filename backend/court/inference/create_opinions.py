import asyncio

import anthropic
import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
import tqdm
from anthropic import AsyncAnthropic
from rich.console import Console
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
from court.utils.print import CONSOLE

_ANTHROPIC_API_KEY = rl.utils.io.getenv("ANTHROPIC_API_KEY")

_DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
_DEFAULT_CONCURRENCY = 4
_CREATOR_NAME = "claude-sonnet-4-5-20250929"
_TASK_NAME = "create_opinions"
_RECORD_TYPE = "fantasy_court_opinions"

_SYSTEM_PROMPT = """You are a judicial clerk for the Fantasy Court, a tribunal that adjudicates fantasy football disputes on "The Ringer Fantasy Football Show" podcast.

The hosts—Chief Justice Danny Heifetz, Justice Danny Kelly, and Justice Craig Horlbeck—hear cases and render decisions in each episode's Fantasy Court segment. Your role is to draft formal legal opinions memorializing these decisions.

## Your Task

You will draft a complete Fantasy Court opinion for a specific case. You will be provided:
- Full case information (caption, facts, questions presented, procedural posture)
- Episode metadata (title, date, etc.)
- Transcript excerpt of the hosts' discussion of this case
- Access to all previously decided Fantasy Court opinions via tools

Your opinion must faithfully reflect the conclusion and reasoning articulated by the justices in the podcast episode, while exercising appropriate creative license in formalizing the legal analysis and developing the Fantasy Court's common law.

## Workflow

1. **Analyze the transcript**: Read the provided transcript excerpt carefully to understand:
   - The hosts' ultimate conclusion (who prevailed, what relief was granted/denied)
   - The key reasoning and legal principles they invoked
   - Any entertaining asides, hypotheticals, or commentary worth incorporating
   - Which justice(s) agreed/dissented

2. **Review precedent**: Use the `list_past_opinions` tool to see what cases have been decided previously. Identify 2-4 cases that are potentially relevant based on:
   - Similar topics or legal issues
   - Applicable legal frameworks or tests
   - Useful analogies or distinctions

3. **Study relevant cases**: Use the `read_past_opinion` tool to read the full text of selected opinions. Consider how to cite and build upon these precedents. You can call this tool multiple times in parallel for efficiency.

4. **Draft the opinion**: Compose all required fields (described below) using formal legal prose, then submit via `submit_opinion` tool.

## Required Fields

### 1. Authorship HTML (authorship_html)
Specifies who wrote the opinion and how other justices aligned.

**Format**: Use `<span class="small-caps">` for justice names.

**Examples**:
- Majority with dissent: `<span class="small-caps">Justice Horlbeck</span> delivered the opinion of the Court, in which <span class="small-caps">Chief Justice Heifetz</span> joined. <span class="small-caps">Justice Kelly</span> filed a dissenting opinion.`
- Majority (unanimous, typical for simple cases and pick the host who feels most strongly): `<span class="small-caps">Justice Horlbeck</span> delivered the opinion for a unanimous Court.`
- Per curiam (unanimous, if hosts are all uniform or not strongly opinionated): `<span class="small-caps">Per Curiam</span>.`
- Concurrence in part: `<span class="small-caps">Justice Kelly</span> delivered the opinion of the Court, in which <span class="small-caps">Justice Horlbeck</span> joined and <span class="small-caps">Justice Heifetz</span> joined as to parts I and II. <span class="small-caps">Chief Justice Heifetz</span> filed an opinion concurring in part and dissenting in part.`

If the hosts are split on something - it can be a fun opportunity to have a fractured court with concurrences or dissents! But don't force it.

Try to distribute majority opinion assignments relatively evenly, with the Chief Justice getting close cases as the most senior justice.

### 2. Holding Statement HTML (holding_statement_html)
A single-sentence summary of the Court's holding, typically starting with "Held:".

**Length**: 1-2 sentences maximum.

**Format**: Use `<em>Held:</em>` prefix. Be specific about what was decided.

**Examples**:
- `<em>Held:</em> Retroactive roster substitutions to accommodate a spouse's active labor constitute permissible force majeure relief under Fantasy Court precedent.`
- `<em>Held:</em> Blackmail—specifically, threatening to disclose a league member's conduct to his spouse in exchange for favorable trade consideration—violates fundamental principles of fair dealing and is categorically impermissible.`
- `<em>Held:</em> Trade made by league commissioner with his father-in-law immediately following news of player injury is voidable where the commissioner possessed material non-public information.`

### 3. Reasoning Summary HTML (reasoning_summary_html)
A 2-4 sentence summary of the legal framework or reasoning applied.

**Purpose**: Provides a condensed version of the Court's analytical approach for future citation.

**Examples**:
- `We applied the established three-factor test for force majeure relief: (1) whether the circumstance was truly extraordinary and unforeseeable; (2) whether the petitioner acted reasonably under the circumstances; and (3) whether granting relief would create moral hazard. We found all three factors satisfied where petitioner faced the imminent birth of his child.`
- `We drew a distinction between permissible gamesmanship and impermissible coercion. While creative tactics are encouraged in fantasy football, threats to disclose embarrassing information to a league member's spouse in exchange for favorable trade consideration constitute duress under contract law principles.`
- `Applying the material-information doctrine from securities law by analogy, we held that commissioners owe fiduciary duties to their leagues. They may not exploit information asymmetries when trading with league members. We distinguished permissible pre-news trading by ordinary managers who owe no such duties.`

### 4. Opinion Body HTML (opinion_body_html)
The full text of the opinion with detailed legal reasoning.

**Length**: 750-1000 words.

**Structure**: Opinions should follow this general structure:

1. **Opening (2-3 paragraphs)**: Brief recounting of the facts and procedural history, followed by statement of the issue and the Court's holding. This primes the reader for the analysis to come.

2. **Part I** (facts and procedural posture, if needed): When the factual or procedural background requires more detail than the opening provides, use Part I for a fuller exposition. For simpler cases, you can skip part headers entirely and proceed directly to the legal analysis.

3. **Part II (and beyond)** (legal analysis): The substantive legal reasoning. Apply precedent, develop doctrine, respond to counterarguments. Complex opinions may use Part III, Part IV, etc. for distinct legal issues or analytical frameworks.

4. **Conclusion**: Brief concluding paragraph. If it flows naturally from the preceding analysis, it can follow immediately. If there's a tonal or structural shift, offset it with a section break (`* * *`).

5. **Disposition**: End every opinion with a formal disposition statement using `<p class="disposition">It is so ordered.</p>` or similar. This is the final, right-aligned declaration of the Court's order.

**When to use part headers**: Use them for opinions with distinct analytical sections or when additional factual exposition is needed beyond the opening. Simpler, more straightforward opinions can flow continuously without part divisions. Think of part headers as organizational tools for complex reasoning, not mandatory formatting.

**Structural markup**:
- Part headers: `<p class="part-header">I</p>`, `<p class="part-header">II</p>`, etc.
- Section breaks: `<p class="section-break">* * *</p>` (use to offset conclusions or create breathing room between major sections)
- Disposition: `<p class="disposition">It is so ordered.</p>` (always the final element, right-aligned)

**Style Guidelines**:
- **Modern legal prose**: Think Kagan, Gorsuch, Newsom, Roberts, Sotomayor circa 2025—not archaic 19th-century English common law
- **Use "we" naturally**: The Court speaks in first person plural ("We hold," "Let us explain," "As we've said")
- **Direct and conversational**: "Let us explain." "That, he may not do." Short, punchy sentences for emphasis.
- **Clear structure**: Use enumeration when laying out tests, alternatives, or factors: "(1) first factor; (2) second factor; (3) third factor"
- **Avoid overly formal or antiquated terms**: Don't use "heretofore," "wherefore," "parturient," "said roster move," etc.
- **Accessible to educated non-lawyers**: Use legal terms of art appropriately but don't over-jargon
- **Dry wit and deadpan humor**: Treat absurd fantasy football situations with complete legal seriousness, which creates the comedy
- **Specific and precise**: Cite player names, scores, dates, league details from the transcript
- **Grounded in transcript**: Don't invent facts not discussed or reasonably inferable from the podcast
- **Natural transitions**: "As we've said," "Let us turn to," "The question becomes," "So [party] cannot"

**Example opening paragraphs** (facts, procedural history, issue, holding):

```html
<p>Petitioner's sister went into labor with her second child. While petitioner and his wife watched their first child, petitioner noticed that his brother-in-law had made several roster moves on the fantasy app at 4:23 PM. The baby was born at 4:30 PM—seven to twelve minutes after the roster transactions. When petitioner mentioned this timeline to his wife, she became immediately furious at her brother's apparent priorities.</p>

<p>Petitioner now seeks a declaratory ruling that he may use this information to extract favorable trade consideration from his brother-in-law in exchange for his silence. We granted review to resolve whether such conduct constitutes permissible gamesmanship or impermissible coercion.</p>

<p>We hold that it does not. Threatening to disclose a league member's conduct to his spouse in exchange for favorable trade consideration violates fundamental principles of fair dealing.</p>
```

**Example with part headers and analytical structure**:

```html
<p class="part-header">I</p>

<p>The factual record is undisputed. Petitioner's brother-in-law made roster moves at 4:23 PM on Sunday, October 15, 2024. His wife delivered their second child seven minutes later. Petitioner learned of this timeline and mentioned it to his own wife, who reacted with understandable dismay. Petitioner now seeks to leverage this information in fantasy football trade negotiations.</p>

<p class="part-header">II</p>

<p>Petitioner's argument is straightforward: All information is fair game in fantasy football. Leveraging information asymmetries, he says, is the essence of successful management. We disagree.</p>

<p>This Court has long recognized a distinction between (1) permissible information-based advantages, and (2) impermissible coercion through threats. The former category includes advantages arising from superior research, attention, or even luck—trading away a player before injury news breaks, for instance. The latter involves using threats to compel favorable terms, particularly threats directed at interests beyond the fantasy league itself. See <span data-cite-docket="24-0142-1"><em>League v. Commissioner</em>, 24-0142-1 (2024)</span> (holding that psychological warfare threatening external relationships is impermissible).</p>

<p>Petitioner's proposed conduct falls squarely in the second category. Threatening to disclose embarrassing information to a league member's spouse—thereby potentially damaging a family relationship—in exchange for favorable trade consideration constitutes duress. See <span data-cite-docket="23-0089-2"><em>In re. Collusion Allegations</em>, 23-0089-2 (2023)</span> (holding that agreements procured through threats are voidable regardless of substantive fairness). That, petitioner may not do.</p>
```

**Example conclusion with section break and disposition**:

```html
<p class="section-break">* * *</p>

<p>Petitioner may not leverage threats of spousal disclosure to extract favorable trade terms. Such conduct constitutes impermissible coercion that taints any resulting agreement. The petition for declaratory relief is denied.</p>

<p class="disposition">It is so ordered.</p>
```

**Alternative conclusion (more direct)**:

```html
<p>Petitioner's proposed scheme crosses the line from gamesmanship to coercion. We hold under well-established fantasy football precedent that such conduct is impermissible.</p>

<p class="disposition">Petition denied.</p>
```

**Common dispositions** (choose one appropriate to the case):
- `<p class="disposition">It is so ordered.</p>` (general affirmation of the Court's ruling)
- `<p class="disposition">Petition granted.</p>`
- `<p class="disposition">Petition denied.</p>`
- `<p class="disposition">Relief granted in part and denied in part.</p>`
- `<p class="disposition">Trade voided.</p>`
- `<p class="disposition">Roster substitution permitted.</p>`
- `<p class="disposition">Affirmed.</p>`
- `<p class="disposition">Reversed.</p>`

**Case Citations**: When citing previous Fantasy Court opinions, use this exact format:

```html
<span data-cite-docket="XX-XXXX-X"><em>Case Caption</em>, XX-XXXX-X (Year)</span>
```

The `data-cite-docket` attribute must contain the docket number (e.g., "25-0197-1"). Follow quasi-Bluebook style:
- Italicize case names with `<em>`
- Include docket number after the case name
- Include year in parentheses
- Add holding parentheticals when helpful for clarity

**Bluebook Citation Signals**: Use appropriate citation signals to indicate the relationship between your assertion and the cited authority:

- **No signal**: Direct support for the stated proposition
  - Example: `Commissioners owe fiduciary duties to their leagues. <span data-cite-docket="25-0012-1"><em>Manager v. Commissioner</em>, 25-0012-1 (2025)</span>.`

- **See**: Cited authority clearly supports the proposition but doesn't directly state it
  - Example: `Threats that harm interests beyond the fantasy league itself are impermissible. See <span data-cite-docket="23-0089-2"><em>In re. Collusion Allegations</em>, 23-0089-2 (2023)</span>.`

- **See also**: Provides additional support; use after already citing direct authority
  - Example: `See <span data-cite-docket="24-0142-1"><em>League v. Commissioner</em>, 24-0142-1 (2024)</span>; see also <span data-cite-docket="23-0089-2"><em>In re. Collusion Allegations</em>, 23-0089-2 (2023)</span>.`

- **Cf.**: Cited authority supports proposition by analogy
  - Example: `The same principle applies here. Cf. <span data-cite-docket="24-0156-2"><em>In re. Trade Veto</em>, 24-0156-2 (2024)</span> (applying similar reasoning in trade veto context).`

- **But see**: Cited authority contradicts the proposition; acknowledge contrary precedent
  - Example: `But see <span data-cite-docket="24-0098-1"><em>In re. Aggressive Tactics</em>, 24-0098-1 (2024)</span> (suggesting broader scope for permissible gamesmanship).`

- **But cf.**: Cited authority contradicts proposition by analogy
  - Example: `But cf. <span data-cite-docket="23-0156-1"><em>Manager v. League</em>, 23-0156-1 (2023)</span> (reaching different result under distinct factual circumstances).`

**Examples with signals and holding parentheticals**:
- `See <span data-cite-docket="24-0156-2"><em>In re. Trade Veto</em>, 24-0156-2 (2024)</span> (establishing three-factor test for collusion).`
- `Cf. <span data-cite-docket="25-0012-1"><em>Manager v. Commissioner</em>, 25-0012-1 (2025)</span> (holding that commissioners owe fiduciary duties).`

**Citing Real Supreme Court Cases**: You may cite famous Supreme Court cases when they are directly on point and help develop the legal reasoning by analogy. Use standard case citation format without the `data-cite-docket` attribute. However, do NOT quote from these cases—paraphrase holdings and reasoning to avoid hallucination risk.

Use such citations sparingly - do at most one per opinion and keep the focus on the main reasoning and where pertinent, Fantasy Court precedent.

**Appropriate uses**:
- Drawing analogies to contract law principles (e.g., duress, good faith)
- Citing fiduciary duty cases when discussing commissioner obligations
- Referencing procedural or remedial doctrines

**Examples**:
- `Drawing on contract law principles of duress, see <em>Williams v. Walker-Thomas Furniture Co.</em>, 350 F.2d 445 (D.C. Cir. 1965), we hold that agreements procured through threats are voidable.`
- `Cf. <em>SEC v. Chenery Corp.</em>, 318 U.S. 80 (1943) (recognizing fiduciary duties in analogous context).`

**Important**: Only cite cases you are confident exist and are on point. When in doubt, rely solely on Fantasy Court precedent.

## Dissenting and Concurring Opinions

When the authorship indicates a justice filed a dissenting or concurring opinion, include it in the same `opinion_body_html` after the majority opinion, separated by a section break.

**Separation**: Use `<p class="opinion-break"></p>` to separate the majority opinion from dissents/concurrences.

**Opening**: Begin with the justice's name in small caps and their role:
- `<p><span class="small-caps">Justice Kelly</span>, dissenting.</p>`
- `<p><span class="small-caps">Justice Horlbeck</span>, with whom <span class="small-caps">Justice Heifetz</span> joins, dissenting.</p>`
- `<p><span class="small-caps">Justice Heifetz</span>, concurring in part and dissenting in part.</p>`

**Structure**: Dissents/concurrences typically:
1. Open with the above identification line
2. Acknowledge the majority's holding (often briefly)
3. Explain the disagreement or additional reasoning
4. May cite precedent differently or distinguish the majority's citations

**Ending**: Dissents/concurrences do NOT use a disposition statement. Simply end with the final substantive paragraph.

**Example with dissent**:
```html
<!-- End of majority opinion -->
<p class="disposition">It is so ordered.</p>

<p class="section-break">* * *</p>

<p><span class="small-caps">Justice Kelly</span>, dissenting.</p>

<p>The majority holds that threatening spousal disclosure constitutes impermissible coercion. I disagree. In fantasy football, all information is fair game, and the majority's ruling improperly limits the creative tactics that make our leagues engaging.</p>

<p><!-- ...rest of dissent... --></p>
```

## HTML Markup Rules

**Allowed tags**:
- `<p>` for paragraphs (required for structure)
- `<p class="part-header">I</p>`, `<p class="part-header">II</p>`, etc. for part headers (Roman numerals)
- `<p class="section-break">* * *</p>` for section breaks (typically before conclusions)
- `<p class="disposition">It is so ordered.</p>` for the final disposition (right-aligned, always the last element)
- `<em>` for case names, Latin phrases, and emphasis
- `<b>` for bold (use very sparingly, typically not needed)
- `<span class="small-caps">` for justice names in authorship field, or references to other justices in the opinion body (such as when referencing a past opinion's author, or the dissent)
- `<span data-cite-docket="XX-XXXX-X">...</span>` for case citations with full citation text inside

**Prohibited**: Do not use `<h1>`, `<h2>`, `<ul>`, `<ol>`, `<li>`, `<div>`, `<br>`, or any other HTML tags not explicitly listed above.

## Important Guidelines

1. **Fidelity to episode**: Your analysis must align with the hosts' reasoning and conclusion. Don't invent a different rationale or reach a different outcome. If they made a joke or hypothetical that illuminates their reasoning, incorporate it appropriately.

2. **Respect the common law**: Use `list_past_opinions` and `read_past_opinion` to understand what precedents exist. Cite relevant cases. Distinguish them when necessary. Build a coherent body of law that develops over time.

3. **Appropriate creativity**: You have significant latitude in:
   - Formalizing the hosts' reasoning into legal doctrine (e.g., creating multi-factor tests)
   - Developing new legal frameworks where none exist
   - Adding color, wit, and judicial personality to the prose
   - Drawing analogies to real legal principles (contracts, torts, constitutional law, etc.)

   But remain grounded in what the hosts actually discussed.

4. **Modern, accessible style**: Write like a contemporary Supreme Court opinion—clear, precise, and occasionally eloquent. Avoid unnecessary jargon and archaic language. The goal is authenticity and humor, not impenetrability.

5. **Length targets**:
   - `authorship_html`: 1-3 sentences
   - `holding_statement_html`: 1-2 sentences
   - `reasoning_summary_html`: 2-3 sentences
   - `opinion_body_html`: 1000-1250 words (roughly 6-8 substantial paragraphs)

6. **Cite specifically**: When discussing facts or applying reasoning, reference specific details from the transcript—player names, point totals, exact timing of events, league rules, etc.

7. **Always include a disposition**: Every opinion must end with a formal disposition statement (e.g., "It is so ordered.", "Petition denied.", "Trade voided."). This is the final, right-aligned element that formally declares the Court's order.

8. If a past opinion is clearly irrelevant from the summary shown, you don't need to read it - you can save the tokens. But don't be too shy.

9. Sometimes due to transcription errors, football players' may be mis-spelled in the provided transcript and information. If the player being referred to is well known to you, you can use your knowledge of the player to correct the spelling.

## Tools Available

**list_past_opinions**: Returns a formatted list of all Fantasy Court opinions with key metadata (ID, docket number, caption, episode info, fact summary, holding, reasoning summary). Use this first to survey the landscape of precedent.

**read_past_opinion**: Takes an `opinion_id` parameter and returns the full text of that opinion including the complete opinion body. Use this to study 2-4 relevant precedents in detail. You can call this tool multiple times in parallel for efficiency.

**submit_opinion**: Submit your completed opinion with these required parameters:
  - `authorship_html` (string)
  - `holding_statement_html` (string)
  - `reasoning_summary_html` (string)
  - `opinion_body_html` (string)

## Working Method

Take your time. Think carefully about:
- What the hosts actually decided and why
- What precedents are relevant and how to cite them
- How to formalize their reasoning into legal doctrine
- How to maintain the right tone (serious legal analysis of absurd situations)

When you're ready, submit your opinion using the `submit_opinion` tool with all four required fields.
"""


def _list_past_opinions(db: Session) -> str:
    """
    List all past Fantasy Court opinions with key metadata.

    Returns a formatted string containing:
    - Total count of opinions
    - For each opinion: ID, docket number, case caption, episode info,
      fact summary, holding statement, and reasoning summary
    """
    query = (
        sa.select(FantasyCourtOpinion)
        .options(
            selectinload(FantasyCourtOpinion.case).selectinload(
                FantasyCourtCase.episode
            )
        )
        .join(FantasyCourtCase, FantasyCourtOpinion.case_id == FantasyCourtCase.id)
        .order_by(FantasyCourtCase.episode_id)  # Chronological order
    )

    opinions = db.execute(query).scalars().all()

    if not opinions:
        return "No past opinions found in the Fantasy Court database."

    lines = [f"Total past opinions: {len(opinions)}\n"]

    for opinion in opinions:
        case = opinion.case
        episode = case.episode
        lines.append(f"Opinion ID: {opinion.id}")
        lines.append(f"Docket Number: {case.docket_number}")
        lines.append(f"Case Caption: {case.case_caption or '(no caption)'}")
        lines.append(
            f"Episode: {episode.title} ({episode.pub_date.strftime('%B %d, %Y')})"
        )
        if case.case_topics:
            lines.append(f"Topics: {', '.join(case.case_topics)}")
        lines.append(f"Fact Summary: {case.fact_summary}")
        lines.append(f"Holding: {opinion.holding_statement_html}")
        lines.append(f"Reasoning Summary: {opinion.reasoning_summary_html}")
        lines.append(f"Authorship: {opinion.authorship_html}")
        lines.append("")  # blank line between opinions

    return "\n".join(lines)


def _read_past_opinion(db: Session, opinion_id: int) -> str:
    """
    Read the full text of a specific opinion by ID.

    Returns a formatted string with all opinion details including the full
    opinion body HTML.
    """
    query = (
        sa.select(FantasyCourtOpinion)
        .options(
            selectinload(FantasyCourtOpinion.case).selectinload(
                FantasyCourtCase.episode
            )
        )
        .where(FantasyCourtOpinion.id == opinion_id)
    )

    opinion = db.execute(query).scalar_one_or_none()

    if not opinion:
        return f"Opinion ID {opinion_id} not found."

    case = opinion.case
    episode = case.episode

    lines = [
        f"Opinion ID: {opinion.id}",
        f"Docket Number: {case.docket_number}",
        f"Case Caption: {case.case_caption or '(no caption)'}",
        f"Episode: {episode.title} ({episode.pub_date.strftime('%B %d, %Y')})",
        "",
        "=== CASE INFORMATION ===",
        "",
        f"Fact Summary: {case.fact_summary}",
        "",
        f"Questions Presented: {case.questions_presented_html or '(none)'}",
        "",
        f"Procedural Posture: {case.procedural_posture or '(none)'}",
        "",
        f"Topics: {', '.join(case.case_topics) if case.case_topics else '(none)'}",
        "",
        "=== OPINION ===",
        "",
        f"Authorship: {opinion.authorship_html}",
        "",
        f"Holding: {opinion.holding_statement_html}",
        "",
        f"Reasoning Summary: {opinion.reasoning_summary_html}",
        "",
        "--- FULL OPINION BODY ---",
        "",
        opinion.opinion_body_html,
    ]

    return "\n".join(lines)


_OPINION_AGENT_TOOLS = [
    {
        "name": "list_past_opinions",
        "description": "List all past Fantasy Court opinions with key metadata (ID, docket number, case caption, episode info, fact summary, holding, reasoning summary). Use this first to survey the landscape of precedent.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_past_opinion",
        "description": "Read the full text of a specific opinion by ID, including the complete opinion body. Use this to study relevant precedents in detail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "opinion_id": {
                    "type": "integer",
                    "description": "The ID of the opinion to read",
                }
            },
            "required": ["opinion_id"],
        },
    },
    {
        "name": "submit_opinion",
        "description": "Submit your completed opinion with all four required fields. This ends the drafting process.",
        "input_schema": {
            "type": "object",
            "properties": {
                "authorship_html": {
                    "type": "string",
                    "description": "The HTML markup for authorship (e.g., which justice wrote the opinion)",
                },
                "holding_statement_html": {
                    "type": "string",
                    "description": "The HTML markup for the holding statement (1-2 sentences starting with <em>Held:</em>)",
                },
                "reasoning_summary_html": {
                    "type": "string",
                    "description": "The HTML markup summarizing the legal reasoning (2-3 sentences)",
                },
                "opinion_body_html": {
                    "type": "string",
                    "description": "The full opinion body HTML (750-1000 words)",
                },
            },
            "required": [
                "authorship_html",
                "holding_statement_html",
                "reasoning_summary_html",
                "opinion_body_html",
            ],
        },
    },
]


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


def _serialize_message_log(messages: list[dict]) -> list[dict]:
    """
    Serialize the message log to a JSON-compatible format.

    Converts Anthropic content blocks to dicts for storage.
    Preserves cache_control and other metadata for debugging.
    """
    serialized = []
    for message in messages:
        serialized_message = {"role": message["role"]}

        # Serialize content
        content = message["content"]
        if isinstance(content, str):
            serialized_message["content"] = content
        elif isinstance(content, list):
            serialized_content = []
            for item in content:
                if isinstance(item, dict):
                    # Already a dict (e.g., tool_result, text with cache_control)
                    serialized_content.append(item)
                elif hasattr(item, "model_dump"):
                    # Pydantic model (thinking block, tool use block, text block)
                    serialized_content.append(item.model_dump())
                else:
                    # Fallback for any other type
                    serialized_content.append(str(item))
            serialized_message["content"] = serialized_content
        else:
            serialized_message["content"] = content

        serialized.append(serialized_message)

    return serialized


async def run_opinion_drafting_agent(
    db: Session,
    client: AsyncAnthropic,
    model: str,
    case: FantasyCourtCase,
) -> FantasyCourtOpinion:
    """
    Run the opinion drafting agent for a case.

    This agent uses interleaved thinking with tool use to:
    1. Analyze the case transcript
    2. Review past opinions for relevant precedent
    3. Draft a complete opinion with all required fields
    4. Submit the opinion via the submit_opinion tool

    Args:
        db: Database session
        client: Anthropic async client
        model: Claude model to use
        case: FantasyCourtCase with episode and segment relationships loaded

    Returns:
        FantasyCourtOpinion object (not yet saved to DB, includes message log)
    """
    # Get the transcript excerpt for this case
    full_transcript = case.segment.transcript.transcript_obj()
    case_transcript = full_transcript.slice(case.start_time_s, case.end_time_s)
    transcript_text = case_transcript.to_string(include_timestamps=True)

    # Build episode context
    episode = case.episode
    episode_context = f"""Episode: {episode.title}
Published: {episode.pub_date.strftime("%B %d, %Y")}
Description: {episode.description_html or "(no description)"}
"""

    # Build case context
    case_context = f"""Docket Number: {case.docket_number}
Case Caption: {case.case_caption or "(not provided)"}
Fact Summary: {case.fact_summary}
"""

    if case.questions_presented_html:
        case_context += f"Questions Presented: {case.questions_presented_html}\n"

    if case.procedural_posture:
        case_context += f"Procedural Posture: {case.procedural_posture}\n"

    if case.case_topics:
        case_context += f"Topics: {', '.join(case.case_topics)}\n"

    # Build initial user message
    user_message = f"""{episode_context}

{case_context}

Transcript of Case Discussion (timestamps relative to episode start):
{transcript_text}

Please draft a complete Fantasy Court opinion for this case. Remember to:
1. Start by analyzing the transcript to understand the hosts' conclusion and reasoning
2. Use the list_past_opinions tool to survey relevant precedent
3. Use the read_past_opinion tool to study 2-4 relevant cases in detail
4. Draft all four required fields (authorship_html, holding_statement_html, reasoning_summary_html, opinion_body_html)
5. Submit your opinion using the submit_opinion tool when ready
"""

    # Initialize message history
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_message,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    CONSOLE.print("[bold blue]Starting agent for case:[/bold blue]")
    CONSOLE.print(f"  Docket: [cyan]{case.docket_number}[/cyan]")
    CONSOLE.print(f"  Caption: [cyan]{case.case_caption or '(no caption)'}[/cyan]")
    CONSOLE.print(f"  Episode: [cyan]{episode.title}[/cyan]\n")

    # Track thinking and tool use blocks across turns
    max_iterations = 20  # Safety limit
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Make API call with interleaved thinking
        # We have to use the `stream` method because Claude API requires us
        #  to use streaming beyond a certain max_tokens limit.
        async with client.beta.messages.stream(
            model=model,
            max_tokens=24000,
            thinking={"type": "enabled", "budget_tokens": 16000},
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=_OPINION_AGENT_TOOLS,
            betas=["interleaved-thinking-2025-05-14"],
            messages=messages,
        ) as stream:
            async for _ in stream:
                pass

        response = await stream.get_final_message()

        # Extract thinking and tool use blocks
        thinking_blocks = [
            block for block in response.content if block.type == "thinking"
        ]
        tool_use_blocks = [
            block for block in response.content if block.type == "tool_use"
        ]
        text_blocks = [block for block in response.content if block.type == "text"]

        CONSOLE.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
        CONSOLE.print(
            f"[bold cyan]Agent Turn {iteration} (Case #{case.id})[/bold cyan]"
        )
        CONSOLE.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

        # Display thinking blocks
        if thinking_blocks:
            for i, thinking_block in enumerate(thinking_blocks, 1):
                # Show a preview of the thinking
                thinking_text = thinking_block.thinking

                CONSOLE.print(f"[bold yellow]💭 Thinking Block {i}:[/bold yellow]")
                CONSOLE.print(f"[dim]{thinking_text}[/dim]\n")

        # Display text blocks if any (usually none with tool use)
        if text_blocks:
            for i, text_block in enumerate(text_blocks, 1):
                CONSOLE.print(f"[bold white]💬 Text Block {i}:[/bold white]")
                CONSOLE.print(f"{text_block.text}\n")

        # If there are no tool uses, we're done (shouldn't happen, but handle it)
        if not tool_use_blocks:
            if text_blocks:
                raise ValueError(
                    f"Agent returned text without submitting opinion: {text_blocks[0].text}"
                )
            raise ValueError("Agent returned no tool uses or text")

        # Add assistant message to history
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Process tool calls
        tool_results = []
        opinion_submitted = False

        for tool_use in tool_use_blocks:
            if tool_use.name == "list_past_opinions":
                CONSOLE.print(
                    "[bold green]🔧 Tool Call:[/bold green] [cyan]list_past_opinions[/cyan]"
                )
                CONSOLE.print(
                    "[dim]Retrieving all past opinions with metadata...[/dim]\n"
                )

                result = _list_past_opinions(db)

                # Count how many opinions were found
                lines = result.split("\n")
                first_line = lines[0] if lines else ""
                CONSOLE.print(f"[green]✓[/green] {first_line}\n")

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }
                )

            elif tool_use.name == "read_past_opinion":
                opinion_id = tool_use.input["opinion_id"]

                CONSOLE.print(
                    f"[bold green]🔧 Tool Call:[/bold green] [cyan]read_past_opinion[/cyan] "
                    f"(opinion_id={opinion_id})"
                )
                CONSOLE.print(
                    f"[dim]Reading full text of opinion {opinion_id}...[/dim]\n"
                )

                result = _read_past_opinion(db, opinion_id)

                if "not found" in result.lower():
                    CONSOLE.print(
                        f"[yellow]⚠[/yellow] Opinion {opinion_id} not found\n"
                    )
                else:
                    # Extract docket number from result
                    for line in result.split("\n"):
                        if line.startswith("Docket Number:"):
                            docket = line.split(":", 1)[1].strip()
                            CONSOLE.print(
                                f"[green]✓[/green] Retrieved opinion {opinion_id} ({docket})\n"
                            )
                            break

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }
                )

            elif tool_use.name == "submit_opinion":
                CONSOLE.print(
                    "[bold green]📝 Tool Call:[/bold green] [cyan]submit_opinion[/cyan]"
                )
                CONSOLE.print(
                    "[bold magenta]Agent is submitting the drafted opinion![/bold magenta]\n"
                )
                # Extract opinion fields
                authorship_html = tool_use.input["authorship_html"]
                holding_statement_html = tool_use.input["holding_statement_html"]
                reasoning_summary_html = tool_use.input["reasoning_summary_html"]
                opinion_body_html = tool_use.input["opinion_body_html"]

                # Serialize message log for storage
                serialized_message_log = _serialize_message_log(messages)

                # Create FantasyCourtOpinion object (not saved to DB yet)
                opinion = FantasyCourtOpinion(
                    case_id=case.id,
                    authorship_html=authorship_html,
                    holding_statement_html=holding_statement_html,
                    reasoning_summary_html=reasoning_summary_html,
                    opinion_body_html=opinion_body_html,
                    agent_message_log=serialized_message_log,
                    # provenance_id will be set by caller
                )

                opinion_submitted = True
                break  # Stop processing other tool calls

        if tool_results:
            # Remove previous cache controls to avoid exceeding the 4-block limit
            _remove_cache_controls(messages)
            tool_results[-1]["cache_control"] = {"type": "ephemeral"}

        # If opinion was submitted, we're done
        if opinion_submitted:
            CONSOLE.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
            CONSOLE.print(
                "[bold green]✓ Opinion drafting completed successfully![/bold green]"
            )
            CONSOLE.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")
            return opinion

        # Otherwise, add tool results to messages and continue loop
        messages.append({"role": "user", "content": tool_results})

    # If we hit max iterations without submitting, raise error
    raise ValueError(
        f"Agent exceeded maximum iterations ({max_iterations}) without submitting opinion"
    )


async def process_cases_batch(
    cases: list[FantasyCourtCase],
    db: Session,
    provenance_id: int,
    model: str,
    concurrency: int,
    commit_batch_size: int = 4,
) -> tuple[int, int]:
    """
    Process a batch of cases with async concurrency in chronological order.

    IMPORTANT: Cases are processed in sequential batches (not all at once) to ensure
    earlier opinions are committed to the database before later opinions are drafted.
    This allows the agent to cite earlier precedents when drafting later opinions,
    building up the common law sequentially.

    Args:
        cases: List of cases to process (with episode and segment relationships loaded,
               ordered by publication date ascending)
        db: Database session
        provenance_id: ID of provenance record
        model: Claude model to use
        concurrency: Number of parallel requests within each batch
        commit_batch_size: Number of opinions to process in each sequential batch

    Returns:
        Tuple of (opinions_created, cases_processed)
    """
    console = Console()
    client = anthropic.AsyncAnthropic(api_key=_ANTHROPIC_API_KEY)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(case: FantasyCourtCase) -> FantasyCourtOpinion | None:
        async with semaphore:
            try:
                opinion = await asyncio.wait_for(
                    run_opinion_drafting_agent(db, client, model, case),
                    timeout=600,  # 10 minutes
                )

                # Assign provenance
                opinion.provenance_id = provenance_id

                return opinion
            except Exception as e:
                console.print(
                    f"[red]Error processing case {case.id} (docket {case.docket_number}):[/red] {e}"
                )
                return None

    total_created = 0
    failed_count = 0

    # Use tqdm to track overall progress
    pbar = tqdm.tqdm(total=len(cases), desc="Drafting opinions")

    # Process cases in sequential batches to build common law chronologically
    for i in range(0, len(cases), commit_batch_size):
        batch = cases[i : i + commit_batch_size]

        # Process this batch concurrently
        tasks = [process_one(case) for case in batch]
        batch_results = await asyncio.gather(*tasks)

        # Commit this batch
        batch_opinions = [opinion for opinion in batch_results if opinion is not None]
        batch_failed = len([opinion for opinion in batch_results if opinion is None])

        if batch_opinions:
            db.add_all(batch_opinions)
            db.commit()
            total_created += len(batch_opinions)

        failed_count += batch_failed
        pbar.update(len(batch))

    pbar.close()

    if failed_count > 0:
        console.print(
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
    help="Number of parallel requests to make",
)
def main(model: str, concurrency: int):
    """Draft Fantasy Court opinions using Claude."""
    console = Console()

    console.print(
        f"\n[bold blue]Drafting Fantasy Court opinions using:[/bold blue] {model}"
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

    # Get cases that don't have opinions yet
    # Must have segment with transcript
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

    cases: list[FantasyCourtCase] = db.execute(cases_query).scalars().all()

    console.print(
        f"[bold]Found {len(cases)} cases with transcripts but no opinions. First case date: {cases[0].episode.pub_date.strftime('%B %d, %Y')}[/bold]\n"
    )

    if not cases:
        console.print("[yellow]No cases to process[/yellow]\n")
        return

    # Process cases
    opinions_created, cases_processed = asyncio.run(
        process_cases_batch(
            cases, db, provenance.id, model, concurrency, commit_batch_size=concurrency
        )
    )

    console.print(
        f"\n[bold green]SUCCESS:[/bold green] Created [bold cyan]{opinions_created}[/bold cyan] "
        f"opinions from [bold]{cases_processed}[/bold] cases processed\n"
    )

    # Display a table with created opinions
    if opinions_created > 0:
        table = Table(
            title="Sample Created Opinions (first 10)",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Docket", style="cyan", width=12)
        table.add_column("Caption", style="green", max_width=40)
        table.add_column("Authorship", style="magenta", max_width=50)

        # Fetch recently created opinions
        recent_opinions: list[FantasyCourtOpinion] = db.execute(
            sa.select(FantasyCourtOpinion)
            .options(selectinload(FantasyCourtOpinion.case))
            .where(FantasyCourtOpinion.provenance_id == provenance.id)
            .order_by(FantasyCourtOpinion.created_at.desc())
            .limit(10)
        ).all()

        for opinion in recent_opinions:
            case = opinion.case
            table.add_row(
                case.docket_number,
                case.case_caption or "(no caption)",
                opinion.authorship_html[:100] + "..."
                if len(opinion.authorship_html) > 100
                else opinion.authorship_html,
            )

        console.print(table)
        console.print()


if __name__ == "__main__":
    main()
