"""Calendar, weather, and global event utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import random
from typing import Any
from zoneinfo import ZoneInfo

from engine.exceptions import ValidationError


WEATHER_TYPES: list[tuple[str, str]] = [
    ("Sunny", "☀️"),
    ("Cloudy", "☁️"),
    ("Rain", "🌧️"),
    ("Storm", "⛈️"),
    ("Windy", "💨"),
    ("Fog", "🌫️"),
    ("Snow", "❄️"),
]

MOON_PHASES: list[str] = [
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent",
]


@dataclass(frozen=True)
class WeatherInfo:
    weather_type: str
    emoji: str
    moon_phase: str


def validate_timezone(tz_name: str) -> None:
    """Raise ValidationError if timezone is invalid."""
    if tz_name.upper() == "UTC":
        return
    try:
        ZoneInfo(tz_name)
    except Exception as exc:
        raise ValidationError(f"Invalid timezone '{tz_name}'. Use IANA timezone like UTC or America/New_York.") from exc


def parse_iso_date(raw: str, field_name: str = "date") -> date:
    """Parse YYYY-MM-DD date string or raise ValidationError."""
    try:
        return date.fromisoformat(str(raw))
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name} '{raw}'. Expected YYYY-MM-DD.") from exc


def today_for_timezone(tz_name: str) -> date:
    """Return current date in target timezone."""
    now = datetime.now(timezone_for_name(tz_name))
    return now.date()


def timezone_for_name(tz_name: str) -> timezone | ZoneInfo:
    """Resolve timezone name with UTC fallback for environments missing tzdata."""
    if str(tz_name).upper() == "UTC":
        return timezone.utc
    return ZoneInfo(str(tz_name))


def deterministic_seed_from_text(text: str) -> int:
    """Stable int seed for a text input."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def weather_for_date(seed: int, target_date: date) -> WeatherInfo:
    """Return deterministic weather and moon phase for a given date."""
    rng_seed = f"{seed}:{target_date.isoformat()}"
    rng = random.Random(rng_seed)
    weather_type, emoji = WEATHER_TYPES[rng.randint(0, len(WEATHER_TYPES) - 1)]
    moon_phase = moon_phase_for_date(target_date)
    return WeatherInfo(weather_type=weather_type, emoji=emoji, moon_phase=moon_phase)


def moon_phase_for_date(target_date: date) -> str:
    """Approximate moon phase using known new moon reference."""
    reference_new_moon = date(2000, 1, 6)
    cycle_days = 29.53058867
    days_since = (target_date - reference_new_moon).days
    position = (days_since % cycle_days) / cycle_days
    idx = int(position * 8) % 8
    return MOON_PHASES[idx]


def week_start(target_date: date) -> date:
    """Return Monday of the week for target date."""
    return target_date - timedelta(days=target_date.weekday())


def date_range(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]


def normalize_events(world: dict[str, Any]) -> list[dict[str, Any]]:
    events = world.get("events", {})
    if not isinstance(events, dict):
        return []
    return list(events.values())


def normalize_holidays(world: dict[str, Any]) -> list[dict[str, Any]]:
    holidays = world.get("holidays", {})
    if not isinstance(holidays, dict):
        return []
    return list(holidays.values())


def events_for_day(world: dict[str, Any], target_date: date) -> list[dict[str, Any]]:
    day_events: list[dict[str, Any]] = []
    target = target_date.isoformat()
    for event in normalize_events(world):
        start = str(event.get("start_date", ""))
        end = str(event.get("end_date", start))
        if not start:
            continue
        if start <= target <= end:
            day_events.append(event)

    for holiday in normalize_holidays(world):
        if str(holiday.get("date", "")) == target:
            day_events.append(
                {
                    "id": holiday.get("id"),
                    "name": holiday.get("name"),
                    "description": holiday.get("description", "Holiday"),
                    "type": "holiday",
                }
            )
    return day_events


def to_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
