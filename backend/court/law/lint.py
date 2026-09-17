"""Lint the opinion/ directory of a drafting workspace.

Runnable as `python -m court.law.lint <workspace>`; the workspace's `./lint`
script is a thin wrapper around this so the drafting agent can call it.
"""

import re
import sys
from pathlib import Path

import bs4
import pydantic

from court.law.workspace import OPINION_FILES, html_to_text

_ALLOWED_P_CLASSES = {"part-header", "section-break", "disposition", "opinion-break"}
_ALLOWED_INLINE_TAGS = {"em", "b"}
_DOCKET_RE = re.compile(r"^\d{2}-\d{4}-\d+$")
_MIN_BODY_WORDS = 500
_MAX_BODY_WORDS = 2200


class LintResult(pydantic.BaseModel):
    errors: list[str] = []
    warnings: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = []
        for error in self.errors:
            lines.append(f"error: {error}")
        for warning in self.warnings:
            lines.append(f"warning: {warning}")
        if not lines:
            lines.append("ok: no problems found")
        return "\n".join(lines)


def known_dockets(workspace: Path) -> set[str]:
    return {p.stem for p in (workspace / "corpus").glob("*.html")}


def _check_markup(
    filename: str, html: str, dockets: set[str], result: LintResult
) -> None:
    """Check that only the allowed tags and attributes appear."""
    soup = bs4.BeautifulSoup(html, "lxml")
    # lxml wraps fragments in html/body; ignore those.
    for tag in soup.find_all(True):
        if tag.name in {"html", "body"}:
            continue
        attrs = dict(tag.attrs)
        if tag.name == "p":
            classes = attrs.pop("class", [])
            bad_classes = set(classes) - _ALLOWED_P_CLASSES
            if bad_classes:
                result.errors.append(
                    f"{filename}: <p> has unknown class {', '.join(sorted(bad_classes))}"
                )
        elif tag.name == "span":
            classes = set(attrs.pop("class", []))
            docket = attrs.pop("data-cite-docket", None)
            if docket is not None:
                docket = str(docket)
                if not _DOCKET_RE.match(docket):
                    result.errors.append(
                        f"{filename}: malformed data-cite-docket {docket!r}"
                    )
                elif docket not in dockets:
                    result.errors.append(
                        f"{filename}: cites docket {docket} which does not exist in corpus/"
                    )
            elif classes != {"small-caps"}:
                result.errors.append(
                    f'{filename}: <span> must have class="small-caps" or data-cite-docket, got {tag.attrs}'
                )
            if classes - {"small-caps"}:
                result.errors.append(
                    f"{filename}: <span> has unknown class {', '.join(sorted(classes - {'small-caps'}))}"
                )
        elif tag.name in _ALLOWED_INLINE_TAGS:
            pass
        else:
            result.errors.append(f"{filename}: prohibited tag <{tag.name}>")
            continue
        if attrs:
            result.errors.append(
                f"{filename}: <{tag.name}> has unexpected attributes {sorted(attrs)}"
            )
    for comment in soup.find_all(string=lambda s: isinstance(s, bs4.Comment)):
        result.errors.append(f"{filename}: HTML comment found: {str(comment)[:60]!r}")


def lint_opinion_files(files: dict[str, str], dockets: set[str]) -> LintResult:
    """Lint opinion content keyed by filename (as in OPINION_FILES)."""
    result = LintResult()
    for filename in OPINION_FILES:
        content = files.get(filename, "").strip()
        if not content:
            result.errors.append(f"{filename}: empty or missing")
            continue
        _check_markup(filename, content, dockets, result)

    holding = files.get("holding_statement.html", "").strip()
    if holding and not holding.startswith("<em>Held:</em>"):
        result.warnings.append(
            "holding_statement.html: should start with <em>Held:</em>"
        )

    body = files.get("opinion_body.html", "").strip()
    if body:
        if 'class="disposition"' not in body:
            result.errors.append(
                'opinion_body.html: no <p class="disposition"> found; every majority opinion needs one'
            )
        if "<p" not in body:
            result.errors.append("opinion_body.html: no <p> paragraphs found")
        words = len(html_to_text(body).split())
        if words < _MIN_BODY_WORDS:
            result.warnings.append(
                f"opinion_body.html: only {words} words; target is 1000-1250 for the majority"
            )
        elif words > _MAX_BODY_WORDS:
            result.warnings.append(
                f"opinion_body.html: {words} words; target is 1000-1250 for the majority. Trim."
            )
    return result


def lint_workspace(workspace: Path) -> LintResult:
    opinion_dir = workspace / "opinion"
    files = {
        filename: (opinion_dir / filename).read_text()
        if (opinion_dir / filename).exists()
        else ""
        for filename in OPINION_FILES
    }
    return lint_opinion_files(files, known_dockets(workspace))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m court.law.lint <workspace>", file=sys.stderr)
        return 2
    result = lint_workspace(Path(argv[0]))
    print(result.render())
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
