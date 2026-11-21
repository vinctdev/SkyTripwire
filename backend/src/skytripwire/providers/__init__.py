"""Data source providers."""

import importlib

from skytripwire.config import Settings
from skytripwire.providers.adsblol import AdsbLolProvider
from skytripwire.providers.base import (
    Aircraft,
    AreaQuery,
    GlobalField,
    GlobalQuery,
    Provider,
    ProviderBlockedError,
    ProviderError,
    ProviderUnavailableError,
    Query,
    RateLimitedError,
)

__all__ = [
    "Aircraft",
    "AreaQuery",
    "GlobalField",
    "GlobalQuery",
    "Provider",
    "ProviderBlockedError",
    "ProviderError",
    "ProviderUnavailableError",
    "Query",
    "RateLimitedError",
    "build_providers",
]


def build_providers(settings: Settings) -> list[Provider]:
    """Create the enabled providers. adsb.lol is always on, FR24 only when enabled."""
    api_key = settings.adsblol_api_key.get_secret_value() if settings.adsblol_api_key else None
    providers: list[Provider] = [AdsbLolProvider(settings.adsblol_base_url, api_key)]
    if settings.fr24_enabled:
        try:
            # Imported lazily: the FR24 extra is optional for native installs.
            fr24 = importlib.import_module("skytripwire.providers.fr24")
        except ImportError as exc:
            raise RuntimeError(
                "FR24 is enabled but the optional dependencies are missing. "
                "Install them with: pip install 'skytripwire[fr24]'"
            ) from exc
        fr24_provider: Provider = fr24.Fr24Provider()
        providers.append(fr24_provider)
    return providers
