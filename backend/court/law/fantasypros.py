"""FantasyPros data for the drafting agent, under a strict call budget.

Runnable as `python -m court.law.fantasypros --workspace <dir> <command>`; unlisted
case workspaces get a `./fantasypros` wrapper around this, like `./lint`.

The free API tier allows 50 calls a day, returns at most 10 records per call, and
has no name search. So players are resolved to FantasyPros IDs locally with the
DynastyProcess ID crosswalk, every call is filtered to specific players, responses
are cached, and calls count against a daily and a per-workspace budget.
"""

import csv
import datetime
import hashlib
import json
import re
from pathlib import Path

import httpx
import pydantic
import rl.utils.click as click
import rl.utils.io

_BASE_URL = "https://api.fantasypros.com/public/v2/json"
_CROSSWALK_URL = (
    "https://github.com/dynastyprocess/data/raw/master/files/db_playerids.csv"
)
_CROSSWALK_MAX_AGE = datetime.timedelta(days=7)
_CACHE_TTL = datetime.timedelta(hours=6)
_DAILY_LIMIT = 40
"""Of the plan's 50 calls a day, leaving headroom for manual use."""
_WORKSPACE_LIMIT = 12
_MAX_PLAYERS_PER_CALL = 10
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


class CrosswalkPlayer(pydantic.BaseModel):
    fpid: int
    name: str
    position: str
    team: str
    age: str
    season: int


def _data_dir() -> Path:
    path = rl.utils.io.get_data_path("fantasypros")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def current_season() -> int:
    """The NFL season in progress, rolling over on June 1."""
    now = _now()
    return now.year if now.month >= 6 else now.year - 1


def _normalize_name(name: str) -> str:
    words = re.sub(r"[^a-z ]", "", name.lower().replace("-", " ")).split()
    return " ".join(word for word in words if word not in _NAME_SUFFIXES)


def load_crosswalk() -> list[CrosswalkPlayer]:
    """Players with a FantasyPros ID, downloaded weekly from DynastyProcess."""
    path = _data_dir() / "db_playerids.csv"
    stale = (
        not path.exists()
        or _now() - datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.UTC)
        > _CROSSWALK_MAX_AGE
    )
    if stale:
        response = httpx.get(_CROSSWALK_URL, follow_redirects=True, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    players = []
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("fantasypros_id", "").isdigit():
                continue
            players.append(
                CrosswalkPlayer(
                    fpid=int(row["fantasypros_id"]),
                    name=row["name"],
                    position=row["position"],
                    team=row["team"],
                    age=row["age"],
                    season=int(row["db_season"]) if row["db_season"].isdigit() else 0,
                )
            )
    return players


def find_players(query: str, crosswalk: list[CrosswalkPlayer]) -> list[CrosswalkPlayer]:
    """Crosswalk players matching a name (exact, then substring) or a numeric ID."""
    if query.isdigit():
        return [p for p in crosswalk if p.fpid == int(query)] or [
            CrosswalkPlayer(
                fpid=int(query),
                name=f"#{query}",
                position="?",
                team="?",
                age="?",
                season=0,
            )
        ]
    target = _normalize_name(query)
    matches = [p for p in crosswalk if _normalize_name(p.name) == target]
    if not matches:
        matches = [p for p in crosswalk if target in _normalize_name(p.name)]
    # Prefer players active in the most recent season of the crosswalk.
    if len(matches) > 1:
        latest = max(p.season for p in matches)
        matches = [p for p in matches if p.season == latest]
    return matches


def resolve_players(queries: tuple[str, ...]) -> list[CrosswalkPlayer]:
    crosswalk = load_crosswalk()
    resolved = []
    for query in queries:
        matches = find_players(query, crosswalk)
        if not matches:
            raise click.ClickException(
                f"No player matches {query!r}. Try `find` with a shorter name, or pass a FantasyPros ID."
            )
        if len(matches) > 1:
            options = "\n".join(f"  {_describe(p)}" for p in matches)
            raise click.ClickException(
                f"{query!r} is ambiguous; pass the ID instead:\n{options}"
            )
        resolved.append(matches[0])
    if len(resolved) > _MAX_PLAYERS_PER_CALL:
        raise click.ClickException(
            f"At most {_MAX_PLAYERS_PER_CALL} players per call on the free tier"
        )
    return resolved


def _describe(player: CrosswalkPlayer) -> str:
    return f"{player.fpid}  {player.name} ({player.position}, {player.team}, age {player.age})"


def _read_usage() -> dict[str, int]:
    path = _data_dir() / "usage.json"
    return json.loads(path.read_text()) if path.exists() else {}


def _record_call(workspace: Path) -> None:
    usage = _read_usage()
    today = _now().date().isoformat()
    usage[today] = usage.get(today, 0) + 1
    (_data_dir() / "usage.json").write_text(json.dumps(usage, indent=2) + "\n")
    counter = workspace / ".fantasypros_calls"
    calls = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(f"{calls + 1}\n")


def _budget(workspace: Path) -> tuple[int, int]:
    """Remaining (daily, workspace) calls."""
    used_today = _read_usage().get(_now().date().isoformat(), 0)
    counter = workspace / ".fantasypros_calls"
    used_here = int(counter.read_text()) if counter.exists() else 0
    return _DAILY_LIMIT - used_today, _WORKSPACE_LIMIT - used_here


def fetch(workspace: Path, path: str, params: dict[str, str | int]) -> dict:
    """GET an API path, from cache if fresh, otherwise spending one call of budget."""
    cache_key = hashlib.sha256(
        json.dumps([path, sorted(params.items())]).encode()
    ).hexdigest()[:24]
    cache_path = _data_dir() / "cache" / f"{cache_key}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        fetched_at = datetime.datetime.fromisoformat(cached["fetched_at"])
        if _now() - fetched_at < _CACHE_TTL:
            print(f"(cached, fetched {fetched_at:%Y-%m-%d %H:%M} UTC; no call spent)")
            return cached["data"]

    daily, here = _budget(workspace)
    if daily <= 0 or here <= 0:
        raise click.ClickException(
            f"FantasyPros call budget exhausted ({max(daily, 0)} left today, "
            f"{max(here, 0)} left for this case). Proceed without further data."
        )
    api_key = rl.utils.io.getenv("FANTASY_PROS_API_KEY")
    if not api_key:
        raise click.ClickException("FANTASY_PROS_API_KEY is not set")

    _record_call(workspace)
    response = httpx.get(
        f"{_BASE_URL}/{path}",
        params=params,
        headers={"x-api-key": api_key},
        timeout=30,
    )
    if response.status_code == 429:
        raise click.ClickException(
            "FantasyPros rate limit hit. Do not retry; proceed without further data."
        )
    response.raise_for_status()
    data = response.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"fetched_at": _now().isoformat(), "data": data}) + "\n"
    )
    daily, here = _budget(workspace)
    print(
        f"(fetched {_now():%Y-%m-%d %H:%M} UTC; {daily} calls left today, {here} for this case)"
    )
    return data


def _fmt(value: object) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


@click.group()
@click.option(
    "--workspace",
    "-w",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Workspace directory, for the per-case call budget",
)
@click.pass_context
def cli(ctx: click.Context, workspace: Path):
    """FantasyPros consensus data. Players may be given by name or FantasyPros ID."""
    ctx.obj = workspace


@cli.command()
@click.argument("names", nargs=-1, required=True)
def find(names: tuple[str, ...]):
    """Look up players' FantasyPros IDs. Free: no API call."""
    crosswalk = load_crosswalk()
    for name in names:
        matches = find_players(name, crosswalk)
        print(f"{name}:")
        for player in matches or []:
            print(f"  {_describe(player)}")
        if not matches:
            print("  (no match)")


@cli.command()
@click.pass_obj
def budget(workspace: Path):
    """Show remaining API calls. Free: no API call."""
    daily, here = _budget(workspace)
    print(f"{daily} calls left today, {here} left for this case")


@cli.command()
@click.argument("players", nargs=-1, required=True)
@click.option(
    "--week",
    "-k",
    type=int,
    default=None,
    help="Single-week projections instead of rest of season",
)
@click.option(
    "--season", "-s", type=int, default=None, help="Season (default: current)"
)
@click.pass_obj
def projections(
    workspace: Path, players: tuple[str, ...], week: int | None, season: int | None
):
    """Projected fantasy points and stats, rest of season or one week. One call for up to 10 players."""
    resolved = resolve_players(players)
    params: dict[str, str | int] = {
        "position": "ALL",
        "players": ":".join(str(p.fpid) for p in resolved),
    }
    if week is None:
        params["ros"] = "true"
    else:
        params["week"] = week
    data = fetch(workspace, f"nfl/{season or current_season()}/projections", params)
    horizon = f"week {week}" if week is not None else "rest of season"
    print(
        f"FantasyPros consensus projections, {horizon}, season {data.get('season')}, as of week {data.get('week')}"
    )
    for player in data.get("players", []):
        stats = player.get("stats", {})
        print(
            f"- {player['name']} ({player['position_id']}, {player['team_id']}): "
            f"{_fmt(stats.get('points_ppr'))} PPR / {_fmt(stats.get('points_half'))} half / "
            f"{_fmt(stats.get('points'))} std"
        )
        detail = [
            f"{key} {_fmt(value)}"
            for key, value in stats.items()
            if not key.startswith("points") and value
        ]
        if detail:
            print(f"    {', '.join(detail)}")
    returned = {p["fpid"] for p in data.get("players", [])}
    for player in resolved:
        if player.fpid not in returned:
            print(f"- {player.name}: no projection returned")


@cli.command()
@click.argument("player")
@click.option(
    "--season", "-s", type=int, default=None, help="Season (default: current)"
)
@click.pass_obj
def rankings(workspace: Path, player: str, season: int | None):
    """Expert consensus rankings (weekly, rest of season, dynasty) for one player. One call."""
    (resolved,) = resolve_players((player,))
    data = fetch(
        workspace,
        f"nfl/{season or current_season()}/rankings",
        {"player": resolved.fpid, "rankstats": "true"},
    )
    print(
        f"FantasyPros expert consensus rankings, season {data.get('season')}, week {data.get('week')}"
    )
    print(
        "Ranking types: STD/PPR/HALF are this week's rankings by scoring; ROS-* are rest of "
        "season; DYN is dynasty. Each shows rank by position group (FLX = flex, OP = superflex, "
        "ALL = overall), with the expert average and standard deviation."
    )
    for entry in data.get("players", []):
        print(f"- {entry['player_name']} ({entry['position_id']}, {entry['team_id']})")
        rank = entry.get("rank", {})
        ecr, avg, std = (
            rank.get("ECR", {}),
            rank.get("ECR_AVG", {}),
            rank.get("ECR_STD", {}),
        )
        for ranking_type, by_position in ecr.items():
            parts = [
                f"{position} #{value} (avg {_fmt(avg.get(ranking_type, {}).get(position))}, "
                f"sd {_fmt(std.get(ranking_type, {}).get(position))})"
                for position, value in by_position.items()
            ]
            print(f"    {ranking_type}: {'; '.join(parts)}")
    if not data.get("players"):
        print("(no rankings returned)")


@cli.command()
@click.argument("players", nargs=-1, required=True)
@click.pass_obj
def injuries(workspace: Path, players: tuple[str, ...]):
    """Current injury status and practice reports. One call for up to 10 players."""
    resolved = resolve_players(players)
    data = fetch(
        workspace,
        "nfl/injuries",
        {"player_ids": ":".join(str(p.fpid) for p in resolved)},
    )
    print("FantasyPros injury report (current)")
    reported = set()
    for injury in data.get("injuries", []):
        reported.add(injury["player_id"])
        detail = ", ".join(
            f"{key} {injury[key]}"
            for key in ("injury_type", "comment", "ir_weeks", "probability_of_playing")
            if injury.get(key)
        )
        print(
            f"- {injury['name']} ({injury['position_id']}, {injury['team_id']}): "
            f"{injury['status']}, updated {injury['injury_update_date']}"
            + (f"; {detail}" if detail else "")
        )
    for player in resolved:
        if player.fpid not in reported:
            print(f"- {player.name}: no injury designation")


@cli.command()
@click.argument("player")
@click.option("--limit", "-l", type=int, default=5, help="Number of news items")
@click.pass_obj
def news(workspace: Path, player: str, limit: int):
    """Recent news and fantasy analysis for one player. One call."""
    (resolved,) = resolve_players((player,))
    data = fetch(
        workspace, "nfl/news", {"fpid": resolved.fpid, "limit": min(limit, 10)}
    )
    print(f"FantasyPros news for {resolved.name}")
    for item in data.get("items", []):
        print(f"- {item['created']} UTC: {item['title']}")
        if item.get("desc"):
            print(f"    {item['desc']}")
        if item.get("impact"):
            print(f"    Fantasy impact: {item['impact']}")
    if not data.get("items"):
        print("(no news returned)")


if __name__ == "__main__":
    cli()
