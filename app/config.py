import json
from functools import lru_cache

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    aws_region: str = "ap-south-1"

    # Secrets Manager secret holding RDS credentials (JSON: username, password, host, port, dbname, engine)
    db_secret_name: str = "arya/rds-dev"

    # Optional direct override, e.g. for local dev without AWS access. When unset, the DB
    # URL is built from the Secrets Manager secret above.
    database_url: str | None = None

    db_pool_size: int = 5
    db_max_overflow: int = 10

    cognito_user_pool_id: str
    cognito_app_client_id: str
    cognito_region: str = "ap-south-1"

    # Apple's Sign in with Apple identity tokens carry `aud` == the app's bundle id for
    # native (AuthenticationServices) sign-in flows, e.g. "com.aryapet.mvp".
    apple_bundle_id: str

    documents_bucket: str

    sqs_processing_queue_url: str
    sqs_processing_dlq_url: str | None = None

    sns_platform_application_arn: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


def fetch_db_secret(settings: Settings) -> dict:
    client = boto3.client("secretsmanager", region_name=settings.aws_region)
    response = client.get_secret_value(SecretId=settings.db_secret_name)
    return json.loads(response["SecretString"])


def build_database_url(settings: Settings) -> str:
    if settings.database_url:
        return settings.database_url

    secret = fetch_db_secret(settings)
    return (
        f"postgresql+asyncpg://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )
