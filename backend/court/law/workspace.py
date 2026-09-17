"""Materialize a Fantasy Court drafting workspace on disk.

A workspace is a plain directory that a coding agent (or a human) can work in:

    CLAUDE.md          style guide and workflow instructions
    lint               executable that lints opinion/
    workspace.json     case_id and opinion_id this workspace was built from
    case.md            the case and episode context
    transcript.txt     transcript of the hosts discussing the case
    corpus/INDEX.md    one line per past opinion
    corpus/<docket>.txt / .html
    opinion/           the four files that make up an opinion
"""

import json
import re
import stat
import sys
from pathlib import Path

import bs4
import pydantic
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from court.db.models import FantasyCourtCase, FantasyCourtOpinion, PodcastEpisode

_CLAUDE_MD_PATH = Path(__file__).parent / "workspace_claude.md"

OPINION_FILES: dict[str, str] = {
    "authorship.html": "authorship_html",
    "holding_statement.html": "holding_statement_html",
    "reasoning_summary.html": "reasoning_summary_html",
    "opinion_body.html": "opinion_body_html",
}
"""Maps each file in opinion/ to the FantasyCourtOpinion attribute it holds."""

_LINT_SCRIPT = """#!/bin/sh
exec "{python}" -m court.law.lint "$(cd "$(dirname "$0")" && pwd)" "$@"
"""


class WorkspaceMeta(pydantic.BaseModel):
    case_id: int
    docket_number: str
    opinion_id: int | None = None


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def html_to_text(html: str) -> str:
    """Render opinion HTML as plain text, one blank line between paragraphs."""
    soup = bs4.BeautifulSoup(html, "lxml")
    paragraphs = [_collapse_ws(p.get_text()) for p in soup.find_all("p")]
    if not paragraphs:
        return _collapse_ws(soup.get_text())
    return "\n\n".join(p for p in paragraphs if p)


def _opinion_header(opinion: FantasyCourtOpinion) -> list[str]:
    case = opinion.case
    episode = case.episode
    topics = ", ".join(case.case_topics) if case.case_topics else "(none)"
    return [
        f"Docket: {case.docket_number}",
        f"Caption: {case.case_caption or '(no caption)'}",
        f"Episode: {episode.title} ({episode.pub_date.strftime('%B %d, %Y')})",
        f"Topics: {topics}",
        f"Authorship: {html_to_text(opinion.authorship_html)}",
        "",
        f"Facts: {case.fact_summary}",
        "",
        f"Questions Presented: {html_to_text(case.questions_presented_html or '(none)')}",
        "",
        f"Procedural Posture: {case.procedural_posture or '(none)'}",
        "",
        f"Holding: {html_to_text(opinion.holding_statement_html)}",
        "",
        f"Reasoning Summary: {html_to_text(opinion.reasoning_summary_html)}",
    ]


def _write_corpus_entry(corpus_dir: Path, opinion: FantasyCourtOpinion) -> None:
    docket = opinion.case.docket_number
    header = _opinion_header(opinion)
    txt = header + ["", "=== OPINION ===", "", html_to_text(opinion.opinion_body_html)]
    (corpus_dir / f"{docket}.txt").write_text("\n".join(txt) + "\n")
    html = [
        "<!--",
        *header,
        "-->",
        "",
        f"<!-- authorship.html -->\n{opinion.authorship_html}",
        "",
        f"<!-- holding_statement.html -->\n{opinion.holding_statement_html}",
        "",
        f"<!-- reasoning_summary.html -->\n{opinion.reasoning_summary_html}",
        "",
        f"<!-- opinion_body.html -->\n{opinion.opinion_body_html}",
    ]
    (corpus_dir / f"{docket}.html").write_text("\n".join(html) + "\n")


def _index_line(opinion: FantasyCourtOpinion) -> str:
    case = opinion.case
    topics = ", ".join(case.case_topics) if case.case_topics else "none"
    return (
        f"- {case.docket_number} | {case.case_caption or '(no caption)'} | "
        f"{case.episode.pub_date.strftime('%Y-%m-%d')} | topics: {topics} | "
        f"{html_to_text(opinion.authorship_html)} | "
        f"{html_to_text(opinion.holding_statement_html)}"
    )


def write_corpus(db: Session, workspace: Path, case: FantasyCourtCase) -> int:
    """Write past opinions into workspace/corpus. Returns the count written.

    Only opinions from episodes published no later than the case's own episode
    are included, so regenerating an old opinion cannot cite the future.
    """
    corpus_dir = workspace / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    query = (
        sa.select(FantasyCourtOpinion)
        .join(FantasyCourtOpinion.case)
        .join(FantasyCourtCase.episode)
        .options(
            selectinload(FantasyCourtOpinion.case).selectinload(
                FantasyCourtCase.episode
            )
        )
        .where(
            FantasyCourtOpinion.case_id != case.id,
            PodcastEpisode.pub_date <= case.episode.pub_date,
        )
        .order_by(PodcastEpisode.pub_date.asc(), FantasyCourtCase.docket_number)
    )
    opinions = db.execute(query).scalars().all()

    index_lines = [
        "# Fantasy Court Opinions",
        "",
        "Chronological. Each line: docket | caption | date | topics | authorship | holding.",
        f"Full text lives in corpus/<docket>.txt (plain text) and corpus/<docket>.html (markup). {len(opinions)} opinions.",
        "",
    ]
    for opinion in opinions:
        _write_corpus_entry(corpus_dir, opinion)
        index_lines.append(_index_line(opinion))
    (corpus_dir / "INDEX.md").write_text("\n".join(index_lines) + "\n")
    return len(opinions)


def write_case_files(workspace: Path, case: FantasyCourtCase) -> None:
    """Write case.md and transcript.txt for the case being drafted."""
    episode = case.episode
    topics = ", ".join(case.case_topics) if case.case_topics else "(none)"
    case_md = [
        f"# {case.case_caption or '(no caption)'}",
        "",
        f"- Docket: {case.docket_number}",
        f"- Episode: {episode.title}",
        f"- Published: {episode.pub_date.strftime('%B %d, %Y')}",
        f"- Topics: {topics}",
        "",
        "## Facts",
        "",
        case.fact_summary,
        "",
        "## Questions Presented",
        "",
        case.questions_presented_html or "(none)",
        "",
        "## Procedural Posture",
        "",
        case.procedural_posture or "(none)",
        "",
        "## Episode Description",
        "",
        html_to_text(episode.description_html)
        if episode.description_html
        else "(none)",
    ]
    (workspace / "case.md").write_text("\n".join(case_md) + "\n")

    if case.segment.transcript is None:
        raise ValueError(f"Case {case.id} has no transcript")
    transcript = case.segment.transcript.transcript_obj()
    excerpt = transcript.slice(case.start_time_s, case.end_time_s)
    (workspace / "transcript.txt").write_text(
        "Transcript of the hosts' discussion of this case. Timestamps are relative to episode start.\n\n"
        + excerpt.to_string(include_timestamps=True)
        + "\n"
    )


def write_opinion_files(workspace: Path, opinion: FantasyCourtOpinion | None) -> None:
    """Write opinion/, seeded from an existing opinion or empty."""
    opinion_dir = workspace / "opinion"
    opinion_dir.mkdir(parents=True, exist_ok=True)
    for filename, attr in OPINION_FILES.items():
        content = getattr(opinion, attr) if opinion is not None else ""
        (opinion_dir / filename).write_text(content.strip() + "\n" if content else "")


def read_opinion_files(workspace: Path) -> dict[str, str]:
    """Read opinion/ back into a dict keyed by FantasyCourtOpinion attribute."""
    opinion_dir = workspace / "opinion"
    return {
        attr: (opinion_dir / filename).read_text().strip()
        if (opinion_dir / filename).exists()
        else ""
        for filename, attr in OPINION_FILES.items()
    }


def read_meta(workspace: Path) -> WorkspaceMeta:
    return WorkspaceMeta.model_validate_json((workspace / "workspace.json").read_text())


def create_workspace(
    db: Session,
    workspace: Path,
    case: FantasyCourtCase,
    opinion: FantasyCourtOpinion | None = None,
) -> Path:
    """Build a complete drafting workspace for a case in the given directory.

    The case must have its episode and segment (with transcript) loaded.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "CLAUDE.md").write_text(_CLAUDE_MD_PATH.read_text())
    lint_path = workspace / "lint"
    lint_path.write_text(_LINT_SCRIPT.format(python=sys.executable))
    lint_path.chmod(lint_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    meta = WorkspaceMeta(
        case_id=case.id,
        docket_number=case.docket_number,
        opinion_id=opinion.id if opinion is not None else None,
    )
    (workspace / "workspace.json").write_text(
        json.dumps(meta.model_dump(), indent=2) + "\n"
    )
    write_case_files(workspace, case)
    write_corpus(db, workspace, case)
    write_opinion_files(workspace, opinion)
    return workspace
