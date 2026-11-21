"""Application settings, read from environment variables (prefix ``SKYTRIPWIRE_``)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOOPBACK_HOSTS = ("127.0.0.1", "localhost")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SKYTRIPWIRE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Bind to localhost by default. Expose it via a reverse proxy or VPN, there is no login.
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    # Host names the app answers to besides 127.0.0.1 and localhost (comma-separated, without
    # port). Other Host headers get a 400, writes from pages on other hosts a 403. Protects
    # against DNS rebinding and CSRF: without a login, any website could otherwise reach the app
    # on 127.0.0.1 through the browser. Add your domain when using a reverse proxy.
    # "*" turns both checks off.
    allowed_hosts: Annotated[list[str], NoDecode] = []

    data_dir: Path = Path("data")
    # Built web UI (`npm run build` output). Unset: the copy bundled with the package, if any.
    # Without a build the app serves only the API.
    frontend_dir: Path | None = None

    # adsb.lol (default provider). Without a key the limit is 500 requests per day and IP.
    adsblol_base_url: str = "https://api.adsb.lol"
    adsblol_api_key: SecretStr | None = None
    # Requests per rolling 24 hours. Keep a margin below the real limit (500 without key,
    # 1,000 or 7,200 with a free key).
    adsblol_daily_budget: int = Field(default=450, ge=1)

    # Flightradar24 via the unofficial FlightRadarAPI library. Opt-in, personal use only.
    fr24_enabled: bool = False
    # No published limit. Default: at most one request per minute on average.
    fr24_daily_budget: int = Field(default=1440, ge=1)

    # Polling worker.
    worker_enabled: bool = True
    # Lower bound for the cycle interval, even if the budget would allow more.
    poll_min_interval_seconds: int = Field(default=60, ge=10)
    # Protects against notification floods, e.g. on the first cycle of a broad filter.
    max_alerts_per_filter_per_cycle: int = Field(default=10, ge=1)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @property
    def trusted_hosts(self) -> list[str]:
        """Always includes the loopback names (the health check and local access use them)."""
        return list(dict.fromkeys([*LOOPBACK_HOSTS, *self.allowed_hosts]))

    def daily_budgets(self) -> dict[str, int]:
        return {"adsblol": self.adsblol_daily_budget, "fr24": self.fr24_daily_budget}

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'skytripwire.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
