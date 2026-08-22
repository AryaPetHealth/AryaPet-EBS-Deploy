import pytest


@pytest.fixture(autouse=True)
def aws_env(monkeypatch: pytest.MonkeyPatch):
    from app.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "ap-south-1_test")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("APPLE_BUNDLE_ID", "com.aryapet.mvp.test")
    monkeypatch.setenv("S3_DOCUMENTS_BUCKET", "test-bucket")
    monkeypatch.setenv("SQS_PROCESSING_QUEUE_URL", "https://sqs.ap-south-1.amazonaws.com/000000000000/test-queue")

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
