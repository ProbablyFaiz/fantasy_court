import rl.utils.io
from redis import Redis

FANTASY_COURT_REDIS_HOST = rl.utils.io.getenv("FANTASY_COURT_REDIS_HOST")
FANTASY_COURT_REDIS_PORT = rl.utils.io.getenv("FANTASY_COURT_REDIS_PORT")
FANTASY_COURT_REDIS_DB = rl.utils.io.getenv("FANTASY_COURT_REDIS_DB")


def get_redis_url() -> str:
    if any(
        [
            not FANTASY_COURT_REDIS_HOST,
            not FANTASY_COURT_REDIS_PORT,
            not FANTASY_COURT_REDIS_DB,
        ]
    ):
        raise ValueError(
            "FANTASY_COURT_REDIS_HOST, FANTASY_COURT_REDIS_PORT, and FANTASY_COURT_REDIS_DB must be set"
        )
    return f"redis://{FANTASY_COURT_REDIS_HOST}:{FANTASY_COURT_REDIS_PORT}/{FANTASY_COURT_REDIS_DB}"


def get_redis_connection() -> Redis:
    if any(
        [
            not FANTASY_COURT_REDIS_HOST,
            not FANTASY_COURT_REDIS_PORT,
            not FANTASY_COURT_REDIS_DB,
        ]
    ):
        raise ValueError(
            "FANTASY_COURT_REDIS_HOST, FANTASY_COURT_REDIS_PORT, and FANTASY_COURT_REDIS_DB must be set"
        )
    return Redis(
        host=FANTASY_COURT_REDIS_HOST,
        port=FANTASY_COURT_REDIS_PORT,
        db=FANTASY_COURT_REDIS_DB,
    )
