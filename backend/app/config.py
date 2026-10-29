"""Runtime configuration. Everything comes from environment variables (see .env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'foodmania.db'}"
    secret_key: str = "dev-only-change-me"
    public_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_ttl_hours: int = 12

    # DEMO_MODE enables the demo clock (X-Demo-Time header) and simulated checkout.
    demo_mode: bool = True

    storage_dir: str = str(BACKEND_DIR / "storage")
    max_upload_mb: int = 10
    max_pdf_pages: int = 20

    # Providers. Only "mock" ships; real providers are adapters added after credentials exist.
    payment_provider: str = "mock"
    payment_webhook_secret: str = "mock-webhook-secret-change-me"
    sms_provider: str = "mock"
    email_provider: str = "mock"

    # Optional LLM. Without a key the deterministic grounded engine is used.
    anthropic_api_key: str | None = None
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_seconds: float = 8.0

    run_background_worker: bool = True
    receipt_ttl_days: int = 90
    contact_retention_days: int = 180


@lru_cache
def get_settings() -> Settings:
    return Settings()
