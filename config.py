"""
config.py

Central place for all configuration. Every value that can change between
your laptop, a test run, and the live Railway deployment lives here and is
read from environment variables (never hardcoded, per the project's
security rules).

Locally, values come from a `.env` file (see `.env.example`) loaded via
python-dotenv / pydantic-settings. In production (Railway), the same
variable names are set as real environment variables in the dashboard.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App / environment -------------------------------------------------
    APP_ENV: str = "development"          # "development" | "production"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # --- Database ------------------------------------------------------------
    # In production this MUST point inside a mounted persistent volume
    # (see DEPLOYMENT.md), otherwise the trade journal is wiped on every deploy.
    DATABASE_PATH: str = "trading_assistant.db"

    # --- Security --------------------------------------------------------
    # Shared secret that TradingView must send back in every webhook payload.
    # Left blank on purpose so the app REFUSES to accept webhooks until you
    # deliberately set it -- this stops someone from feeding fake signals to
    # an unauthenticated endpoint.
    WEBHOOK_SECRET: str = ""
    # Reject any TradingView payload whose timestamp is older (or, allowing
    # for small clock drift, further in the future) than this many seconds.
    WEBHOOK_MAX_AGE_SECONDS: int = 300
    # Simple in-memory rate limit for the public webhook endpoints.
    RATE_LIMIT_PER_MINUTE: int = 30

    # --- Telegram ----------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # --- Account / risk rules ----------------------------------------------
    ACCOUNT_BALANCE: float = 10_000.0
    RISK_PER_TRADE_PERCENT: float = 0.5      # default risk per trade, in %
    MAX_DAILY_LOSS_PERCENT: float = 1.0
    MAX_WEEKLY_LOSS_PERCENT: float = 3.0
    MAX_CONCURRENT_TRADES: int = 2
    MIN_RISK_REWARD: float = 2.0             # minimum acceptable reward:risk
    MIN_SIGNAL_SCORE: int = 75               # minimum 100-point score to qualify

    # --- Signal lifecycle ----------------------------------------------------
    # NOTE: this is a naive wall-clock timer for now. Stage 2 replaces this
    # with trading-time-aware expiry (weekends don't count). Do not treat
    # this value as final -- it is intentionally the simplest possible
    # implementation so Stage 1 (deployment) is not blocked on it.
    PENDING_SIGNAL_EXPIRY_HOURS: float = 48.0

    # --- Monitoring ----------------------------------------------------------
    MONITOR_INTERVAL_SECONDS: int = 300  # 5 minutes, per spec's initial minimum


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance -- import and call this, don't instantiate
    Settings() directly elsewhere, so the whole app shares one config."""
    return Settings()


def configure_logging(settings: Settings | None = None) -> None:
    """Structured-ish logging setup. Called once at app startup.

    Never logs secret values -- callers must not pass tokens/secrets into
    log messages. See README for the logging convention used in this repo.
    """
    settings = settings or get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
