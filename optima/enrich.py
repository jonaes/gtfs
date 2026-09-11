import pandas as pd
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from gtfs_time import (
    datetime_to_gtfs_minutes,
    gtfs_minutes_to_datetime,
    gtfs_time_to_minutes,
    minutes_to_gtfs_time,
)

TRIPS_FILE = "trips.txt"
TIMELINE_FILE = "timeline.csv"
FAHRPLAN_FILE = "optima_fahrplan.json"
STOPS_FILE = "stops.txt"
AGENCY_FILE = "agency.txt"
OUTPUT_FILE = "stop_times.txt"


def load_fahrplan():
    with open(FAHRPLAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_agency_timezone() -> ZoneInfo:
    agency = pd.read_csv(AGENCY_FILE)
    if agency.empty or not agency.iloc[0].get("agency_timezone"):
        raise ValueError("❌ agency_timezone fehlt in agency.txt")
    return ZoneInfo(str(agency.iloc[0]["agency_timezone"]).strip())


def load_stop_timezones():
    stops = pd.read_csv(STOPS_FILE)
    if "stop_timezone" not in stops.columns:
        raise ValueError("❌ stop_timezone fehlt in stops.txt")

    result = {}
    for _, row in stops.iterrows():
        stop_id = str(row["stop_id"]).strip()
        timezone_name = str(row["stop_timezone"]).strip()
        if not timezone_name or timezone_name.lower() == "nan":
            raise ValueError(f"❌ stop_timezone fehlt für {stop_id}")
        result[stop_id] = ZoneInfo(timezone_name)
    return result


def local_timeline_time_to_gtfs_minutes(
    value: str,
    local_departure_date,
    stop_timezone: ZoneInfo,
    service_date,
    agency_timezone: ZoneInfo,
) -> int:
    """
    Konvertiert eine lokale Referenzzeit aus timeline.csv in echte GTFS-Minuten.

    timeline.csv benutzt lokale Uhrzeiten mit Stunden > 24 relativ zum lokalen
    Abfahrtstag. Durch die Umrechnung des resultierenden timezone-aware datetime
    ueber datetime_to_gtfs_minutes werden Zeitzonengrenzen und DST-Wechsel
    korrekt als verstrichene Zeit behandelt.
    """
    raw_minutes = gtfs_time_to_minutes(value)
    local_day_offset, minute_of_day = divmod(raw_minutes, 24 * 60)
    local_hour, local_minute = divmod(minute_of_day, 60)

    local_date = local_departure_date + timedelta(days=local_day_offset)
    local_dt = datetime.combine(
        local_date,
        time(local_hour, local_minute),
        tzinfo=stop_timezone,
    )

    return datetime_to_gtfs_minutes(
        local_dt,
        service_date,
        agency_timezone,
    )


def normalize_timeline(
    t_section: pd.DataFrame,
    service_date,
    actual_start_min: int,
    stop_timezones,
    agency_timezone: ZoneInfo,
):
    """
    Normalisiert die lokale Referenz-Timeline auf eine echte GTFS-Zeitachse.

    Erst danach werden die relativen Laufzeitanteile skaliert. Damit entstehen
    an Zeitzonengrenzen oder bei Sommer-/Winterzeitwechseln keine kuenstlichen
    Stunden.
    """
    first_stop_id = str(t_section.iloc[0]["stop_id"]).strip()
    if first_stop_id not in stop_timezones:
        raise ValueError(f"❌ Keine Zeitzone für {first_stop_id}")

    actual_departure_agency = gtfs_minutes_to_datetime(
        actual_start_min,
        service_date,
        agency_timezone,
    )
    local_departure_date = actual_departure_agency.astimezone(
        stop_timezones[first_stop_id]
    ).date()

    normalized = t_section.copy()

    for idx, row in normalized.iterrows():
        stop_id = str(row["stop_id"]).strip()
        if stop_id not in stop_timezones:
            raise ValueError(f"❌ Keine Zeitzone für {stop_id}")

        stop_timezone = stop_timezones[stop_id]
        normalized.at[idx, "arrival_min"] = local_timeline_time_to_gtfs_minutes(
            str(row["arrival_time"]),
            local_departure_date,
            stop_timezone,
            service_date,
            agency_timezone,
        )
        normalized.at[idx, "departure_min"] = local_timeline_time_to_gtfs_minutes(
            str(row["departure_time"]),
            local_departure_date,
            stop_timezone,
            service_date,
            agency_timezone,
        )

    return normalized


def enrich_stop_times():
    print(
        f"📥 Lade {TRIPS_FILE}, {TIMELINE_FILE}, {FAHRPLAN_FILE}, "
        f"{STOPS_FILE} und {AGENCY_FILE} ..."
    )
    trips = pd.read_csv(TRIPS_FILE)
    timeline = pd.read_csv(TIMELINE_FILE)
    fahrplan = load_fahrplan()
    agency_timezone = load_agency_timezone()
    stop_timezones = load_stop_timezones()

    all_stop_times = []

    for idx, trip in trips.iterrows():
        trip_id = str(trip["trip_id"]).strip()
        headsign = str(trip["trip_headsign"]).strip().upper()
        richtung = "E" if "EDIRNE" in headsign else "V"

        try:
            fahrdaten = fahrplan[idx]
            abfahrt = fahrdaten["abfahrt_uhrzeit"]
            ankunft = fahrdaten["gtfs_arrival"]
            verkehrstage = fahrdaten["verkehrstage"]
        except IndexError:
            raise ValueError(f"❌ Kein Fahrplaneintrag für trip {trip_id} (Index {idx})")

        if not verkehrstage:
            raise ValueError(f"❌ Keine Verkehrstage für {trip_id}")

        # Eine Variante wird bereits nach ihren tatsaechlichen GTFS-Endzeiten
        # gruppiert. Ein repräsentativer Verkehrstag reicht daher fuer die
        # zeitbezogene Normalisierung ihrer Referenz-Timeline aus.
        service_date = datetime.strptime(verkehrstage[0], "%d.%m.%Y").date()

        start_min = gtfs_time_to_minutes(abfahrt)
        end_min = gtfs_time_to_minutes(ankunft)
        actual_duration = end_min - start_min
        if actual_duration <= 0:
            raise ValueError(f"❌ Ungültige Zeitspanne für {trip_id}: {abfahrt} → {ankunft}")

        t_section = timeline[timeline["trip_direction"] == richtung].copy()
        t_section.sort_values("stop_sequence", inplace=True)

        if t_section.empty:
            raise ValueError(f"❌ Keine Timeline für Richtung {richtung}")

        t_normalized = normalize_timeline(
            t_section,
            service_date,
            start_min,
            stop_timezones,
            agency_timezone,
        )

        ref_start = int(t_normalized.iloc[0]["departure_min"])
        ref_end = int(t_normalized.iloc[-1]["arrival_min"])
        ref_duration = ref_end - ref_start

        if ref_duration <= 0:
            raise ValueError(
                f"❌ Ungültige normalisierte Referenzdauer für {trip_id}: "
                f"{ref_start} → {ref_end}"
            )

        for _, row in t_normalized.iterrows():
            normalized_times = {}
            for source_col, normalized_col in [
                ("arrival_time", "arrival_min"),
                ("departure_time", "departure_min"),
            ]:
                ref_min = float(row[normalized_col])
                offset = ref_min - ref_start
                scaled_min = start_min + (offset / ref_duration) * actual_duration
                normalized_times[source_col] = minutes_to_gtfs_time(
                    scaled_min,
                    with_seconds=True,
                )

            all_stop_times.append({
                "trip_id": trip_id,
                "arrival_time": normalized_times["arrival_time"],
                "departure_time": normalized_times["departure_time"],
                "stop_id": row["stop_id"],
                "stop_sequence": row["stop_sequence"],
                "pickup_type": None,
                "drop_off_type": None,
                "timepoint": 0
            })

    df = pd.DataFrame(all_stop_times)
    df.sort_values(["trip_id", "stop_sequence"], inplace=True)

    df["pickup_type"] = 1
    df["drop_off_type"] = 1

    firsts = df.groupby("trip_id").first().reset_index()
    lasts = df.groupby("trip_id").last().reset_index()

    for _, r in firsts.iterrows():
        df.loc[
            (df["trip_id"] == r["trip_id"]) & (df["stop_sequence"] == r["stop_sequence"]),
            ["pickup_type", "drop_off_type", "timepoint"]
        ] = [0, 1, 1]

    for _, r in lasts.iterrows():
        df.loc[
            (df["trip_id"] == r["trip_id"]) & (df["stop_sequence"] == r["stop_sequence"]),
            ["pickup_type", "drop_off_type"]
        ] = [1, 0]

    df.to_csv(OUTPUT_FILE, index=False)
    print(
        f"✅ {OUTPUT_FILE} geschrieben mit {len(df)} Einträgen "
        f"in {agency_timezone.key}."
    )


if __name__ == "__main__":
    enrich_stop_times()
