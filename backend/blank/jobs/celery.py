from celery import Celery, signals

from blank.db.redis import get_redis_url
from blank.jobs.schedule import BEAT_SCHEDULE
from blank.utils.observe import safe_init_sentry


@signals.celeryd_init.connect
def init_sentry(**_kwargs):
    safe_init_sentry()


def get_celery_app() -> Celery:
    app = Celery("blank", broker=get_redis_url(), include=["blank.jobs.tasks"])

    # Configure Celery
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        enable_utc=True,
        worker_concurrency=4,
        beat_schedule=BEAT_SCHEDULE,
    )

    return app


# Create singleton instance
celery_app = get_celery_app()
