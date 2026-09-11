from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def service_day_anchor(service_date, agency_timezone: ZoneInfo) -> datetime:
    """
    Liefert den GTFS-Tagesanfang als UTC-Zeitpunkt.

    GTFS definiert Time als verstrichene Zeit seit "noon minus 12h" des
    Verkehrstags. Das ist an normalen Tagen identisch mit 00:00 Ortszeit,
    bleibt aber auch ueber Sommer-/Winterzeitwechsel eindeutig.
    """
    noon_local = datetime.combine(
        service_date,
        time(12, 0),
        tzinfo=agency_timezone,
    )
    return noon_local.astimezone(timezone.utc) - timedelta(hours=12)


def datetime_to_gtfs_minutes(
    dt: datetime,
    service_date,
    agency_timezone: ZoneInfo,
) -> int:
    """Konvertiert einen timezone-aware datetime in GTFS-Minuten."""
    if dt.tzinfo is None:
        raise ValueError("datetime muss eine Zeitzone besitzen")

    anchor = service_day_anchor(service_date, agency_timezone)
    delta = dt.astimezone(timezone.utc) - anchor
    seconds = delta.total_seconds()

    if seconds < 0:
        raise ValueError("Zeit liegt vor dem GTFS-Verkehrstag")
    if seconds % 60 != 0:
        raise ValueError("GTFS-Zeit ist nicht minutengenau")

    return int(seconds // 60)


def gtfs_minutes_to_datetime(
    minutes: int,
    service_date,
    agency_timezone: ZoneInfo,
) -> datetime:
    """Konvertiert GTFS-Minuten zurueck in einen datetime der agency_timezone."""
    if minutes < 0:
        raise ValueError("GTFS-Minuten duerfen nicht negativ sein")

    anchor = service_day_anchor(service_date, agency_timezone)
    return (anchor + timedelta(minutes=minutes)).astimezone(agency_timezone)


def gtfs_time_to_minutes(value: str) -> int:
    """Parst HH:MM oder HH:MM:SS; HH darf groesser als 23 sein."""
    parts = value.strip().split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"Ungueltige GTFS-Zeit: {value!r}")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2]) if len(parts) == 3 else 0

    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"Ungueltige GTFS-Zeit: {value!r}")
    if seconds != 0:
        raise ValueError("Dieses Skript verarbeitet nur minutengenaue Zeiten")

    return hours * 60 + minutes


def minutes_to_gtfs_time(minutes: float, with_seconds: bool = True) -> str:
    """Formatiert Minuten als GTFS HH:MM[:SS], auch fuer Werte > 24 h."""
    total = round(minutes)
    if total < 0:
        raise ValueError("GTFS-Minuten duerfen nicht negativ sein")

    hours, minute = divmod(total, 60)
    result = f"{hours:02}:{minute:02}"
    return result + ":00" if with_seconds else result
