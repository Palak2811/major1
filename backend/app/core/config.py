from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PrepPath API"
    app_env: str = "development"

    # SQLite works with zero setup; hosted Postgres+pgvector (e.g. Neon) for real runs:
    # postgresql+asyncpg://USER:PASS@HOST/DB?ssl=require
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    # Optional. Empty => in-process fallbacks (no cache, no rate limiting, tasks run in-process).
    redis_url: str = ""

    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    cookie_secure: bool = False

    # Comma-separated allowlist
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    # Google OAuth2 â€” leave client id empty to run in clearly-labelled mock mode
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/api/v1/auth/google/callback"

    # Phase 1: limiter is wired but disabled by default (real limits land in Phase 5)
    rate_limit_enabled: bool = False

    # Judge0 CE public instance (free, no key) — wired in Phase 3
    judge0_url: str = "https://ce.judge0.com"
    judge0_api_key: str = ""

    # LLM — Google Gemini free tier. Empty key => clearly-labelled mock mode.
    gemini_api_key: str = ""
    llm_model_fast: str = "gemini-flash-lite-latest"
    llm_model_strong: str = "gemini-flash-latest"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    # Cost & reliability controls for AI endpoints
    ai_requests_per_minute: int = 12  # per user
    ai_daily_token_budget: int = 150_000  # per user, prompt + completion
    ai_cache_ttl_seconds: int = 6 * 3600
    uploads_dir: str = "./uploads"
    max_upload_mb: int = 5

    # Seed accounts
    seed_admin_email: str = "admin@preppath.dev"
    seed_admin_password: str = "ChangeMe-Admin1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_mock_mode(self) -> bool:
        return not self.gemini_api_key

    @property
    def google_mock_mode(self) -> bool:
        return not self.google_client_id


@lru_cache
def get_settings() -> Settings:
    return Settings()
