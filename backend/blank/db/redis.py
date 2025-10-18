import rl.utils.io
from redis import Redis

BLANK_REDIS_HOST = rl.utils.io.getenv("BLANK_REDIS_HOST")
BLANK_REDIS_PORT = rl.utils.io.getenv("BLANK_REDIS_PORT")
BLANK_REDIS_DB = rl.utils.io.getenv("BLANK_REDIS_DB")


def get_redis_url() -> str:
    if any(
        [
            not BLANK_REDIS_HOST,
            not BLANK_REDIS_PORT,
            not BLANK_REDIS_DB,
        ]
    ):
        raise ValueError(
            "BLANK_REDIS_HOST, BLANK_REDIS_PORT, and BLANK_REDIS_DB must be set"
        )
    return f"redis://{BLANK_REDIS_HOST}:{BLANK_REDIS_PORT}/{BLANK_REDIS_DB}"


def get_redis_connection() -> Redis:
    if any(
        [
            not BLANK_REDIS_HOST,
            not BLANK_REDIS_PORT,
            not BLANK_REDIS_DB,
        ]
    ):
        raise ValueError(
            "BLANK_REDIS_HOST, BLANK_REDIS_PORT, and BLANK_REDIS_DB must be set"
        )
    return Redis(
        host=BLANK_REDIS_HOST,
        port=BLANK_REDIS_PORT,
        db=BLANK_REDIS_DB,
    )
