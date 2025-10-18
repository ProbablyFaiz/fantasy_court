from celery.schedules import crontab

BEAT_SCHEDULE = {
    "test-job": {
        "task": "blank.jobs.tasks.test_job",
        "schedule": crontab(minute="*/1"),
    },
}
