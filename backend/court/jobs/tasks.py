import subprocess

from court.jobs.celery import celery_app


@celery_app.task
def healthy_job():
    print("healthy_job")


@celery_app.task
def error_job():
    raise Exception("error_job")


@celery_app.task
def run_fantasy_court_pipeline():
    """
    Automated pipeline to process Fantasy Court content end-to-end.

    This task runs every 30 minutes and invokes the `court pipeline run` command.
    """
    subprocess.run(["court", "pipeline", "run"], check=True)
