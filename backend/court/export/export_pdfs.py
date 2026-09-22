"""Typeset each opinion as a slip-opinion PDF booklet with Typst.

The opinion HTML is parsed into a small tree of paragraphs and inline runs and
handed to `opinion.typ` as JSON, so no HTML ever has to be escaped into Typst
markup. Text reaches Typst as plain strings.
"""

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import bs4
import pydantic
import rl.utils.io
import tqdm
import typst
from sqlalchemy.orm import Session

from court.api.interfaces import OpinionRead
from court.db.session import get_session
from court.export.export_opinions import (
    apply_smartypants,
    remove_stale,
    select_opinions,
)

_DEFAULT_OUTPUT_DIR = rl.utils.io.get_data_path("export", "pdfs")
_DEFAULT_FONT_DIR = Path(__file__).parent / "fonts"
_TEMPLATE_PATH = Path(__file__).parent / "opinion.typ"

_SEPARATE_HEAD_RE = re.compile(r"^(Chief Justice|Justice)\s+(\S+),\s*(.+?)\.?$")


class Inline(pydantic.BaseModel):
    kind: Literal["em", "b", "sc", "cite"]
    docket: str | None = None
    children: list["Inline | str"]


InlineContent = list[Inline | str]


class Block(pydantic.BaseModel):
    kind: Literal[
        "p", "part-header", "section-break", "disposition", "opinion-break", "list"
    ]
    children: InlineContent = []
    items: list[InlineContent] = []


class SeparateOpinion(pydantic.BaseModel):
    heading: InlineContent
    running_head: InlineContent
    blocks: list[Block]


class PdfOpinion(pydantic.BaseModel):
    docket_number: str
    caption: str
    term: str
    year: int
    heard_date: str | None
    decided_date: str
    procedural_posture: str | None
    episode_title: str | None
    segment_times: str | None
    facts: list[Block]
    questions: list[Block]
    holding: list[Block]
    reasoning: list[Block]
    authorship: list[Block]
    majority_head: InlineContent
    majority: list[Block]
    separate: list[SeparateOpinion]


def _inline(node: bs4.PageElement) -> InlineContent:
    if isinstance(node, bs4.Comment):
        return []
    if isinstance(node, bs4.NavigableString):
        text = re.sub(r"\s+", " ", str(node))
        return [text] if text else []
    if not isinstance(node, bs4.Tag):
        return []
    children = [part for child in node.children for part in _inline(child)]
    if node.name in {"em", "i"}:
        return [Inline(kind="em", children=children)]
    if node.name in {"b", "strong"}:
        return [Inline(kind="b", children=children)]
    if node.name == "span" and node.get("data-cite-docket"):
        return [
            Inline(kind="cite", docket=str(node["data-cite-docket"]), children=children)
        ]
    if node.name == "span" and "small-caps" in (node.get("class") or []):
        return [Inline(kind="sc", children=children)]
    return children


def _strip(content: InlineContent) -> InlineContent:
    """Trim whitespace at the edges of a paragraph, as a browser would."""
    content = list(content)
    if content and isinstance(content[0], str):
        content[0] = content[0].lstrip()
    if content and isinstance(content[-1], str):
        content[-1] = content[-1].rstrip()
    return [part for part in content if part != ""]


def html_to_blocks(fragment: str | None) -> list[Block]:
    """Parse an HTML fragment into paragraphs; loose text becomes one paragraph."""
    if not fragment or not fragment.strip():
        return []
    soup = bs4.BeautifulSoup(fragment, "lxml")
    root = soup.body or soup
    blocks: list[Block] = []
    loose: InlineContent = []

    def flush() -> None:
        stripped = _strip(loose)
        if stripped:
            blocks.append(Block(kind="p", children=stripped))
        loose.clear()

    for node in root.children:
        if isinstance(node, bs4.Tag) and node.name == "p":
            flush()
            classes = node.get("class") or []
            kind = next(
                (
                    c
                    for c in (
                        "part-header",
                        "section-break",
                        "disposition",
                        "opinion-break",
                    )
                    if c in classes
                ),
                "p",
            )
            blocks.append(Block(kind=kind, children=_strip(_inline(node))))
        elif isinstance(node, bs4.Tag) and node.name in {"ol", "ul"}:
            flush()
            items = [_strip(_inline(li)) for li in node.find_all("li")]
            blocks.append(Block(kind="list", items=items))
        else:
            loose.extend(_inline(node))
    flush()
    return blocks


def _plain_text(content: InlineContent) -> str:
    return "".join(
        part if isinstance(part, str) else _plain_text(part.children)
        for part in content
    )


def _running_head(heading: InlineContent) -> InlineContent:
    """ "Justice Kelly, with whom ... joins, dissenting." -> KELLY, J., dissenting"""
    text = _plain_text(heading).strip()
    match = _SEPARATE_HEAD_RE.match(text)
    if not match:
        return [text.rstrip(".")]
    title = "C. J." if match[1] == "Chief Justice" else "J."
    role = match[3].split(", ")[-1]
    return [Inline(kind="sc", children=[f"{match[2]}, {title}"]), f", {role}"]


def split_separate_opinions(
    blocks: list[Block],
) -> tuple[list[Block], list[SeparateOpinion]]:
    """Split the body at opinion breaks; each separate writing leads with its heading."""
    segments: list[list[Block]] = [[]]
    for block in blocks:
        if block.kind == "opinion-break":
            segments.append([])
        else:
            segments[-1].append(block)
    separate = []
    for segment in segments[1:]:
        if not segment:
            continue
        heading, *rest = segment
        separate.append(
            SeparateOpinion(
                heading=heading.children,
                running_head=_running_head(heading.children),
                blocks=rest,
            )
        )
    return segments[0], separate


def _format_date(value: datetime) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def build_pdf_opinion(opinion: OpinionRead) -> PdfOpinion:
    case = opinion.case
    decided = case.decided_date
    # Like the October Term, a September Term runs from one kickoff to the next.
    term_year = decided.year if decided.month >= 9 else decided.year - 1
    majority, separate = split_separate_opinions(
        html_to_blocks(opinion.opinion_body_html)
    )
    holding = html_to_blocks(opinion.holding_statement_html)
    reasoning = html_to_blocks(opinion.reasoning_summary_html)
    if [_plain_text(b.children) for b in reasoning] == [
        _plain_text(b.children) for b in holding
    ]:
        reasoning = []
    per_curiam = (
        "per curiam"
        in _plain_text(
            [
                part
                for b in html_to_blocks(opinion.authorship_html)
                for part in b.children
            ]
        ).lower()
    )
    segment_times = None
    if case.start_time_s is not None and case.end_time_s is not None:
        segment_times = f"{_format_timestamp(case.start_time_s)}–{_format_timestamp(case.end_time_s)}"
    return PdfOpinion(
        docket_number=case.docket_number,
        caption=html.unescape(case.case_caption or "Untitled Case"),
        term=f"September Term, {term_year}",
        year=decided.year,
        heard_date=_format_date(case.episode.pub_date) if case.episode else None,
        decided_date=_format_date(decided),
        procedural_posture=html.unescape(case.procedural_posture)
        if case.procedural_posture
        else None,
        episode_title=html.unescape(case.episode.title) if case.episode else None,
        segment_times=segment_times if case.episode else None,
        facts=html_to_blocks(case.fact_summary),
        questions=html_to_blocks(case.questions_presented_html),
        holding=holding,
        reasoning=reasoning,
        authorship=html_to_blocks(opinion.authorship_html),
        majority_head=[Inline(kind="sc", children=["Per Curiam"])]
        if per_curiam
        else ["Opinion of the Court"],
        majority=majority,
        separate=separate,
    )


def make_compiler(font_dir: Path) -> typst.Compiler:
    fonts = sorted(font_dir.glob("*.otf"))
    if not fonts:
        raise FileNotFoundError(
            f"No .otf fonts in {font_dir}; copy in the Equity A and "
            "OPTIEngraversOldEnglish faces"
        )
    return typst.Compiler(
        input=str(_TEMPLATE_PATH),
        root=str(_TEMPLATE_PATH.parent),
        font_paths=[str(font_dir)],
        ignore_system_fonts=True,
    )


def render_pdf(compiler: typst.Compiler, opinion: OpinionRead, output_path: Path):
    data = build_pdf_opinion(opinion)
    compiler.compile(
        output=str(output_path),
        sys_inputs={"opinion": data.model_dump_json()},
    )


def export_pdfs(output_dir: Path, font_dir: Path) -> None:
    """Write opinions/{docket_number}.pdf for every opinion, listed or not."""
    session: Session = get_session()
    output_dir.mkdir(parents=True, exist_ok=True)
    compiler = make_compiler(font_dir)

    opinions = session.execute(select_opinions()).scalars().all()
    pbar = tqdm.tqdm(opinions, desc="Typesetting opinions")
    for opinion in pbar:
        opinion_read = apply_smartypants(OpinionRead.model_validate(opinion))
        docket = opinion_read.case.docket_number
        pbar.set_postfix({"docket": docket})
        render_pdf(compiler, opinion_read, output_dir / f"{docket}.pdf")

    remove_stale(output_dir, "pdf", {o.case.docket_number for o in opinions})

    print(f"Typeset {len(opinions)} opinions to {output_dir}")
