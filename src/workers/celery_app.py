from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forecast",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.tasks.training"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_routes={
        "tasks.run_forecast_pipeline": {"queue": "forecast"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)
