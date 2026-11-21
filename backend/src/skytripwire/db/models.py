"""Database tables.

Validation of user input (e.g. min <= max, known emitter categories) happens in the API
schemas. The database only enforces what keeps the data consistent.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

from skytripwire.db.types import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


class FilterChannelLink(SQLModel, table=True):
    """Which notification channels a filter sends to."""

    __tablename__ = "filter_channels"

    filter_id: int = Field(foreign_key="filters.id", primary_key=True, ondelete="CASCADE")
    channel_id: int = Field(foreign_key="channels.id", primary_key=True, ondelete="CASCADE")


class Filter(SQLModel, table=True):
    """A user defined flight filter. Empty criteria lists mean "any"."""

    __tablename__ = "filters"
    __table_args__ = (
        CheckConstraint(
            "(area_latitude IS NULL AND area_longitude IS NULL AND area_radius_nm IS NULL)"
            " OR (area_latitude IS NOT NULL AND area_longitude IS NOT NULL"
            " AND area_radius_nm > 0)",
            name="area_complete",
        ),
        CheckConstraint("cooldown_minutes >= 0", name="cooldown_non_negative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    enabled: bool = True

    # Area: map point + radius. All three NULL means worldwide.
    area_latitude: float | None = None
    area_longitude: float | None = None
    area_radius_nm: float | None = None

    # Criteria. Lists are OR within a field, fields are AND with each other.
    type_codes: list[str] = Field(default_factory=list, sa_type=JSON)
    registrations: list[str] = Field(default_factory=list, sa_type=JSON)
    callsigns: list[str] = Field(default_factory=list, sa_type=JSON)
    airlines: list[str] = Field(default_factory=list, sa_type=JSON)
    squawks: list[str] = Field(default_factory=list, sa_type=JSON)
    # ADS-B emitter categories, e.g. "A7" helicopter, "B1" glider, "B2" balloon, "B6" drone.
    categories: list[str] = Field(default_factory=list, sa_type=JSON)
    # None: any, True: only military, False: exclude military.
    military: bool | None = None
    emergency_only: bool = False
    include_on_ground: bool = False
    altitude_min_ft: int | None = None
    altitude_max_ft: int | None = None
    ground_speed_min_kts: float | None = None
    ground_speed_max_kts: float | None = None
    # Only usable with the FR24 provider (IATA codes).
    origin_airports: list[str] = Field(default_factory=list, sa_type=JSON)
    destination_airports: list[str] = Field(default_factory=list, sa_type=JSON)

    # Do not alert again for the same aircraft and filter within this time.
    cooldown_minutes: int = 60

    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)

    channels: list["Channel"] = Relationship(back_populates="filters", link_model=FilterChannelLink)


class Channel(SQLModel, table=True):
    """A notification target, stored as an Apprise URL. The URL contains secrets."""

    __tablename__ = "channels"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    # "telegram", "email" or "apprise" (free Apprise URL). Drives the form in the UI.
    kind: str
    url: str
    enabled: bool = True

    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)

    filters: list[Filter] = Relationship(back_populates="channels", link_model=FilterChannelLink)


class AlertEvent(SQLModel, table=True):
    """One match of an aircraft against a filter. Also the source for the cooldown."""

    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_cooldown", "filter_id", "aircraft_identity", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    # Kept when the filter is deleted, so the history stays readable.
    filter_id: int | None = Field(
        default=None, foreign_key="filters.id", ondelete="SET NULL", nullable=True
    )
    filter_name: str

    provider: str
    aircraft_identity: str
    hex: str | None = None
    callsign: str | None = None
    registration: str | None = None
    type_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_ft: int | None = None
    ground_speed_kts: float | None = None
    squawk: str | None = None
    origin_iata: str | None = None
    destination_iata: str | None = None
    seen_at: datetime = Field(sa_type=UTCDateTime)

    # "pending", "sent", "failed" or "skipped" (no enabled channel).
    notification_status: str = "pending"
    notification_error: str | None = None

    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime, index=True)


class ProviderState(SQLModel, table=True):
    """Request budget and health per provider, kept across restarts."""

    __tablename__ = "provider_states"

    provider: str = Field(primary_key=True)
    window_started_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    requests_in_window: int = 0
    blocked_until: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_success_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    last_error: str | None = None
    # Drives the exponential backoff, reset on the next success.
    consecutive_failures: int = Field(default=0, sa_column_kwargs={"server_default": "0"})
