"""Request and response models of the REST API.

Input is normalized here (trimmed, uppercase, deduplicated) and validated strictly, so the
database and the engine can trust it. Channel URLs are write-only: responses only ever
contain the masked form.
"""

import re
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from skytripwire.notify.apprise_notifier import is_valid_url

MAX_LIST_ITEMS = 50

# ADS-B emitter categories that make sense as a filter.
EMITTER_CATEGORIES: dict[str, str] = {
    "A1": "Light (< 15,500 lbs)",
    "A2": "Small (15,500 to 75,000 lbs)",
    "A3": "Large (75,000 to 300,000 lbs)",
    "A4": "High vortex large (e.g. B757)",
    "A5": "Heavy (> 300,000 lbs)",
    "A6": "High performance",
    "A7": "Rotorcraft (helicopter)",
    "B1": "Glider / sailplane",
    "B2": "Lighter than air (balloon, airship)",
    "B3": "Parachutist / skydiver",
    "B4": "Ultralight / hang glider / paraglider",
    "B6": "Unmanned aerial vehicle (drone)",
    "B7": "Space / trans-atmospheric vehicle",
}

_PATTERNS = {
    "type_codes": re.compile(r"^[A-Z0-9*?]{1,6}$"),
    "registrations": re.compile(r"^[A-Z0-9*?-]{1,12}$"),
    "callsigns": re.compile(r"^[A-Z0-9*?]{1,8}$"),
    "airlines": re.compile(r"^[A-Z]{3}$"),
    "squawks": re.compile(r"^[0-7]{4}$"),
    "origin_airports": re.compile(r"^[A-Z0-9]{3}$"),
    "destination_airports": re.compile(r"^[A-Z0-9]{3}$"),
}

ChannelKind = Literal["telegram", "email", "apprise"]
_SCHEMES: dict[str, tuple[str, ...]] = {"telegram": ("tgram",), "email": ("mailto", "mailtos")}

Name = Annotated[str, Field(min_length=1, max_length=100)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Area(_Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_nm: float = Field(gt=0, le=5000)


class FilterIn(_Strict):
    name: Name
    enabled: bool = True
    area: Area | None = None
    type_codes: list[str] = Field(default_factory=list)
    registrations: list[str] = Field(default_factory=list)
    callsigns: list[str] = Field(default_factory=list)
    airlines: list[str] = Field(default_factory=list)
    squawks: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    military: bool | None = None
    emergency_only: bool = False
    include_on_ground: bool = False
    altitude_min_ft: int | None = Field(default=None, ge=-2000, le=100_000)
    altitude_max_ft: int | None = Field(default=None, ge=-2000, le=100_000)
    ground_speed_min_kts: float | None = Field(default=None, ge=0, le=5000)
    ground_speed_max_kts: float | None = Field(default=None, ge=0, le=5000)
    origin_airports: list[str] = Field(default_factory=list)
    destination_airports: list[str] = Field(default_factory=list)
    cooldown_minutes: int = Field(default=60, ge=0, le=10_080)
    channel_ids: list[int] = Field(default_factory=list, max_length=MAX_LIST_ITEMS)

    @field_validator(*_PATTERNS, "categories", mode="before")
    @classmethod
    def _normalize_list(cls, values: object) -> object:
        if not isinstance(values, list):
            return values
        cleaned = [v.strip().upper() if isinstance(v, str) else v for v in values]
        return list(dict.fromkeys(v for v in cleaned if v != ""))

    @field_validator(*_PATTERNS)
    @classmethod
    def _check_pattern(cls, values: list[str], info: ValidationInfo) -> list[str]:
        pattern = _PATTERNS[info.field_name or ""]
        _check_length(values)
        invalid = [v for v in values if not pattern.match(v)]
        if invalid:
            raise ValueError(f"invalid value(s): {', '.join(invalid)}")
        return values

    @field_validator("categories")
    @classmethod
    def _check_categories(cls, values: list[str]) -> list[str]:
        _check_length(values)
        unknown = [v for v in values if v not in EMITTER_CATEGORIES]
        if unknown:
            raise ValueError(f"unknown emitter category: {', '.join(unknown)}")
        return values

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        for low, high, label in (
            (self.altitude_min_ft, self.altitude_max_ft, "altitude"),
            (self.ground_speed_min_kts, self.ground_speed_max_kts, "ground speed"),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError(f"{label}: minimum is greater than maximum")
        self.channel_ids = list(dict.fromkeys(self.channel_ids))
        return self


class FilterOut(BaseModel):
    id: int
    name: str
    enabled: bool
    area: Area | None
    type_codes: list[str]
    registrations: list[str]
    callsigns: list[str]
    airlines: list[str]
    squawks: list[str]
    categories: list[str]
    military: bool | None
    emergency_only: bool
    include_on_ground: bool
    altitude_min_ft: int | None
    altitude_max_ft: int | None
    ground_speed_min_kts: float | None
    ground_speed_max_kts: float | None
    origin_airports: list[str]
    destination_airports: list[str]
    cooldown_minutes: int
    channel_ids: list[int]
    created_at: datetime
    updated_at: datetime
    # Which data sources serve this filter, or why none can (from the request planner).
    served_by: list[str]
    unplannable_reason: str | None


class ChannelIn(_Strict):
    name: Name
    kind: ChannelKind
    url: str = Field(min_length=1, max_length=2000)
    enabled: bool = True

    @model_validator(mode="after")
    def _check_url(self) -> Self:
        _validate_url(self.kind, self.url)
        return self


class ChannelUpdate(_Strict):
    """Like :class:`ChannelIn`, but ``url`` may be left out to keep the stored one."""

    name: Name
    kind: ChannelKind
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    enabled: bool = True

    @model_validator(mode="after")
    def _check_url(self) -> Self:
        if self.url is not None:
            _validate_url(self.kind, self.url)
        return self


class ChannelTest(_Strict):
    kind: ChannelKind
    url: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def _check_url(self) -> Self:
        _validate_url(self.kind, self.url)
        return self


class ChannelOut(BaseModel):
    id: int
    name: str
    kind: str
    url_masked: str
    enabled: bool
    filter_ids: list[int]
    created_at: datetime
    updated_at: datetime


class ChannelTestResult(BaseModel):
    ok: bool
    error: str | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filter_id: int | None
    filter_name: str
    provider: str
    aircraft_identity: str
    hex: str | None
    callsign: str | None
    registration: str | None
    type_code: str | None
    latitude: float | None
    longitude: float | None
    altitude_ft: int | None
    ground_speed_kts: float | None
    squawk: str | None
    origin_iata: str | None
    destination_iata: str | None
    seen_at: datetime
    notification_status: str
    notification_error: str | None
    created_at: datetime


class ProviderStatus(BaseModel):
    name: str
    provides: list[str]
    daily_budget: int
    requests_in_window: int
    window_started_at: datetime | None
    planned_requests_per_cycle: int
    blocked_until: datetime | None
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None


class UnplannableFilter(BaseModel):
    filter_id: int
    filter_name: str
    reason: str


class WorkerStatusOut(BaseModel):
    enabled: bool
    last_cycle_started_at: datetime | None
    last_cycle_finished_at: datetime | None
    next_cycle_at: datetime | None
    interval_seconds: float | None
    last_error: str | None
    last_requests_sent: int | None
    last_aircraft_seen: int | None
    last_new_alerts: int | None
    provider_issues: dict[str, str]


class StatusOut(BaseModel):
    worker: WorkerStatusOut
    providers: list[ProviderStatus]
    unplannable: list[UnplannableFilter]


class CategoryOut(BaseModel):
    code: str
    label: str


class ConfigOut(BaseModel):
    version: str
    fr24_enabled: bool
    providers: list[str]
    min_poll_interval_seconds: int
    categories: list[CategoryOut]


def _check_length(values: list[str]) -> None:
    if len(values) > MAX_LIST_ITEMS:
        raise ValueError(f"at most {MAX_LIST_ITEMS} values allowed")


def _validate_url(kind: str, url: str) -> None:
    schemes = _SCHEMES.get(kind)
    if schemes is not None and url.split("://", 1)[0].lower() not in schemes:
        raise ValueError(f"a {kind} channel needs a URL starting with {' or '.join(schemes)}://")
    if not is_valid_url(url):
        # Do not echo the URL, it may contain secrets.
        raise ValueError("not a valid Apprise URL")
