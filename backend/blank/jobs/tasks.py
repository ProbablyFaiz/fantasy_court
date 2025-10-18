from blank.jobs.celery import celery_app


@celery_app.task
def healthy_job():
    print("healthy_job")


@celery_app.task
def error_job():
    raise Exception("error_job")
