"""CLI commands for working with Fantasy Court drafting workspaces."""

import datetime
import mimetypes
from pathlib import Path

import rl.utils.click as click
import rl.utils.io
import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from court.db.models import FantasyCourtCase, FantasyCourtOpinion, FantasyCourtSegment
from court.db.session import get_session
from court.inference.utils import get_or_create_provenance
from court.law import lint as lint_module
from court.law import workspace as workspace_module
from court.utils import bucket
from court.utils.print import CONSOLE

_DEFAULT_WORKSPACE_ROOT = rl.utils.io.get_data_path("workspaces")


@click.group()
def law():
    """Fantasy Court drafting workspace utilities."""
    rl.utils.io.ensure_dotenv_loaded()


def load_case_for_drafting(db: Session, case_id: int) -> FantasyCourtCase:
    """Load a case with everything a workspace needs, or raise a ClickException."""
    case = db.execute(
        sa.select(FantasyCourtCase)
        .where(FantasyCourtCase.id == case_id)
        .options(
            selectinload(FantasyCourtCase.episode),
            selectinload(FantasyCourtCase.segment).selectinload(
                FantasyCourtSegment.transcript
            ),
            selectinload(FantasyCourtCase.opinion),
        )
    ).scalar_one_or_none()
    if case is None:
        raise click.ClickException(f"Case {case_id} not found")
    if not case.unlisted and (case.segment is None or case.segment.transcript is None):
        raise click.ClickException(f"Case {case_id} has no transcript")
    return case


def next_misc_docket_number(db: Session, year: int) -> str:
    """The next docket number on the miscellaneous docket for unlisted cases, e.g. 26-M-3."""
    prefix = f"{year % 100:02d}-M-"
    existing = (
        db.execute(
            sa.select(FantasyCourtCase.docket_number).where(
                FantasyCourtCase.docket_number.startswith(prefix)
            )
        )
        .scalars()
        .all()
    )
    last = max((int(docket.removeprefix(prefix)) for docket in existing), default=0)
    return f"{prefix}{last + 1}"


@law.command("file-case")
@click.option(
    "--caption", "-t", type=str, required=True, help='Case caption, e.g. "Alec v. Nick"'
)
@click.option(
    "--record-path",
    "-r",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Markdown or text file with the written record (accounts, rules, chat logs)",
)
@click.option(
    "--exhibit-path",
    "-e",
    "exhibit_paths",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Exhibit file (PDF, image) to upload; repeat for more, in exhibit order",
)
def file_case(caption: str, record_path: Path | None, exhibit_paths: tuple[Path, ...]):
    """File an unlisted case directly with the Court, without a podcast episode.

    Uploads exhibits to the bucket and creates the case on the miscellaneous
    docket. Draft it with `court inference draft-opinion -c <id>`.
    """
    if record_path is None and not exhibit_paths:
        raise click.ClickException(
            "Provide a --record-path, at least one --exhibit-path, or both"
        )

    db = get_session()
    docket_number = next_misc_docket_number(
        db, datetime.datetime.now(datetime.UTC).year
    )
    bucket_paths = []
    if exhibit_paths:
        client = bucket.get_bucket_client()
        for path in exhibit_paths:
            bucket_path = f"exhibits/{docket_number}/{path.name}"
            content_type, _ = mimetypes.guess_type(path.name)
            bucket.write_file(path, bucket_path, client, content_type=content_type)
            bucket_paths.append(bucket_path)
            CONSOLE.print(f"[dim]Uploaded {path} to {bucket_path}[/dim]")

    provenance = get_or_create_provenance(
        db, task_name="file_case", creator_name="cli", record_type="fantasy_court_cases"
    )
    case = FantasyCourtCase(
        provenance_id=provenance.id,
        docket_number=docket_number,
        case_caption=caption,
        fact_summary="",
        unlisted=True,
        record_text=record_path.read_text() if record_path is not None else None,
        exhibit_paths=bucket_paths or None,
    )
    db.add(case)
    db.commit()
    CONSOLE.print(
        f"[green]Filed case {case.id}[/green] {caption}, docket {docket_number}"
    )
    CONSOLE.print(
        f"[dim]Draft it with: court inference draft-opinion -c {case.id}[/dim]"
    )


@law.command()
@click.option("--case-id", "-c", type=int, required=True, help="Case to materialize")
@click.option(
    "--dir",
    "-d",
    "workspace_dir",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Workspace directory (default: {_DEFAULT_WORKSPACE_ROOT}/<docket>)",
)
def materialize(case_id: int, workspace_dir: Path | None):
    """Build a drafting workspace for a case, seeded with its existing opinion if any.

    Run `claude` inside the directory to draft or edit, then `court law import`.
    """
    db = get_session()
    case = load_case_for_drafting(db, case_id)
    workspace_dir = workspace_dir or _DEFAULT_WORKSPACE_ROOT / case.docket_number
    workspace_module.create_workspace(db, workspace_dir, case, case.opinion)
    CONSOLE.print(f"[green]Workspace written to[/green] {workspace_dir}")
    if case.opinion is not None:
        CONSOLE.print(f"[dim]Seeded from opinion {case.opinion.id}[/dim]")


@law.command("lint")
@click.option(
    "--dir",
    "-d",
    "workspace_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Workspace directory",
)
def lint_cmd(workspace_dir: Path):
    """Lint the opinion/ directory of a workspace."""
    result = lint_module.lint_workspace(workspace_dir)
    CONSOLE.print(result.render())
    if not result.ok:
        raise click.ClickException("lint failed")


@law.command("import")
@click.option(
    "--dir",
    "-d",
    "workspace_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Workspace directory",
)
@click.option("--force", "-f", is_flag=True, help="Import even if lint reports errors")
def import_cmd(workspace_dir: Path, force: bool):
    """Write a workspace's opinion/ back to the database.

    Updates the case's existing opinion in place, or creates one if none exists.
    """
    result = lint_module.lint_workspace(workspace_dir)
    CONSOLE.print(result.render())
    if not result.ok and not force:
        raise click.ClickException("lint failed; fix the problems or pass --force")

    db = get_session()
    meta = workspace_module.read_meta(workspace_dir)
    fields = workspace_module.read_opinion_files(workspace_dir)
    if meta.unlisted:
        case = db.get_one(FantasyCourtCase, meta.case_id)
        for attr, value in workspace_module.read_case_field_files(
            workspace_dir
        ).items():
            setattr(case, attr, value)
    opinion = db.execute(
        sa.select(FantasyCourtOpinion).where(
            FantasyCourtOpinion.case_id == meta.case_id
        )
    ).scalar_one_or_none()
    if opinion is None:
        provenance = get_or_create_provenance(
            db,
            task_name="import_opinion",
            creator_name="workspace_import",
            record_type="fantasy_court_opinions",
        )
        opinion = FantasyCourtOpinion(
            case_id=meta.case_id, provenance_id=provenance.id, **fields
        )
        db.add(opinion)
    else:
        for attr, value in fields.items():
            setattr(opinion, attr, value)
    db.commit()
    CONSOLE.print(
        f"[green]Imported opinion {opinion.id} for docket {meta.docket_number}[/green]"
    )
