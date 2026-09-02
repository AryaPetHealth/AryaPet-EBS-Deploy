import json
from functools import lru_cache

import boto3
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"
    aws_region: str = "ap-south-1"

    # Secrets Manager secret holding RDS credentials (JSON: username, password, host, port, dbname, engine).
    # Accepts either a friendly secret name or a full ARN (both are valid SecretId values), since the EB
    # environment sets this as DB_SECRET_ARN.
    db_secret_name: str = Field("arya/rds-dev", validation_alias="DB_SECRET_ARN")

    # Optional direct override, e.g. for local dev without AWS access. When unset, the DB
    # URL is built from the Secrets Manager secret above.
    database_url: str | None = None

    db_pool_size: int = 5
    db_max_overflow: int = 10

    cognito_user_pool_id: str
    cognito_app_client_id: str
    cognito_region: str = "ap-south-1"

    # Enables POST /v1/auth/dev-token, which mints a self-signed bearer token (see
    # app/auth/dev_token.py) instead of going through Cognito/Apple. Must stay false
    # outside local/dev — never set this in the prod EB environment.
    dev_auth_enabled: bool = Field(False, validation_alias="DEV_AUTH_ENABLED")

    # Apple's Sign in with Apple identity tokens carry `aud` == the app's bundle id for
    # native (AuthenticationServices) sign-in flows, e.g. "com.aryapet.mvp".
    apple_bundle_id: str

    # Google's identity tokens carry `aud` == this OAuth client id. Optional (unlike
    # apple_bundle_id) so a missing value fails only the /v1/auth/google route at
    # request time, not Settings() validation for the whole app - the deploy incident
    # from a missing *required* var here should not repeat for an optional feature.
    google_client_id: str | None = Field(None, validation_alias="GOOGLE_CLIENT_ID")

    # EB environment sets this as S3_DOCUMENTS_BUCKET.
    documents_bucket: str = Field(validation_alias="S3_DOCUMENTS_BUCKET")

    sqs_processing_queue_url: str
    sqs_processing_dlq_url: str | None = None

    # EB environment sets this as SNS_APNS_PLATFORM_APP_ARN.
    sns_platform_application_arn: str | None = Field(None, validation_alias="SNS_APNS_PLATFORM_APP_ARN")


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
