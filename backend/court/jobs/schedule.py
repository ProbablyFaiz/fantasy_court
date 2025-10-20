from celery.schedules import crontab

BEAT_SCHEDULE = {
    "fantasy-court-pipeline": {
        "task": "court.jobs.tasks.run_fantasy_court_pipeline",
        "schedule": crontab(minute="*/30"),  # Run every 30 minutes
    },
}
