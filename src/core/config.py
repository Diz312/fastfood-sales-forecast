from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://forecast:changeme_dev@localhost:5432/forecast_db"
    database_url_sync: str = "postgresql://forecast:changeme_dev@localhost:5432/forecast_db"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_artifact_root: str = "s3://mlflow-artifacts/"
    mlflow_s3_endpoint_url: str = "http://localhost:9000"

    # MinIO / S3
    minio_endpoint: str = "http://localhost:9000"
    aws_access_key_id: str = "minioadmin"
    aws_secret_access_key: str = "minioadmin123"

    # Anthropic
    anthropic_api_key: str = ""

    # Forecast defaults
    default_horizon_days: int = 365
    default_cv_folds: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
