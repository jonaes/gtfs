import pandas as pd
import json
from datetime import datetime

TRIPS_FILE = "trips.txt"
TIMELINE_FILE = "timeline.csv"
FAHRPLAN_JSON = "optima_fahrplan.json"
OUTPUT_FILE = "stop_times.txt"

def time_to_minutes(t: str) -> int:
    """Wandelt 'HH:MM' oder 'HH:MM:SS' in Minuten um"""
    parts = list(map(int, t.split(":")))
    return parts[0] * 60 + parts[1]

def minutes_to_gtfs(t: float) -> str:
    """Wandelt Minuten (auch >24h) in 'HH:MM:SS'"""
    total = round(t)
    h, m = divmod(total, 60)
    return f"{int(h):02}:{int(m):02}:00"

def load_fahrplandaten():
    with open(FAHRPLAN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def enrich_stop_times():
    print(f"🔄 Lade {TRIPS_FILE} ...")
    trips = pd.read_csv(TRIPS_FILE)
    print(f"📊 Lade {TIMELINE_FILE} ...")
    timeline = pd.read_csv(TIMELINE_FILE)
    fahrplandaten = load_fahrplandaten()

    all_stop_times = []

    for _, trip in trips.iterrows():
        trip_id = trip["trip_id"]
        headsign = trip["trip_headsign"].strip().upper()
        richtung = "E" if "EDIRNE" in headsign else "V"

        # Hole Fahrtzeiten aus Fahrplandaten
        trip_info = next(t for t in fahrplandaten if t["trip_id"] == trip_id)
        start_min = time_to_minutes(trip_info["abfahrt_uhrzeit"])
        end_min = time_to_minutes(trip_info["gtfs_arrival"])
        actual_duration = end_min - start_min
        if actual_duration <= 0:
            raise ValueError(f"❌ Ungültige Zeitspanne für trip {trip_id}")

        # Timeline dieser Richtung
        t_section = timeline[timeline["trip_direction"] == richtung].copy()
        t_section.sort_values("stop_sequence", inplace=True)

        # Referenzdauer = max departure_time
        ref_start = time_to_minutes(t_section.iloc[0]["departure_time"])
        ref_end = time_to_minutes(t_section.iloc[-1]["arrival_time"])
        ref_duration = ref_end - ref_start

        for _, row in t_section.iterrows():
            for time_type in ["arrival_time", "departure_time"]:
                ref_minutes = time_to_minutes(row[time_type])
                relative_offset = ref_minutes - ref_start
                scaled_minutes = start_min + (relative_offset / ref_duration) * actual_duration
                row[time_type] = minutes_to_gtfs(scaled_minutes)

            all_stop_times.append({
                "trip_id": trip_id,
                "arrival_time": row["arrival_time"],
                "departure_time": row["departure_time"],
                "stop_id": row["stop_id"],
                "stop_sequence": row["stop_sequence"],
                "pickup_type": 1,
                "drop_off_type": 1
            })

    df = pd.DataFrame(all_stop_times)

    # Nur erster Halt = timepoint 1
    df["timepoint"] = 0
    firsts = df.sort_values("stop_sequence").groupby("trip_id").first().reset_index()
    for _, r in firsts.iterrows():
        df.loc[
            (df["trip_id"] == r["trip_id"]) &
            (df["stop_sequence"] == r["stop_sequence"]),
            "timepoint"
        ] = 1

    df.sort_values(["trip_id", "stop_sequence"], inplace=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ {OUTPUT_FILE} geschrieben mit {len(df)} Einträgen.")

if __name__ == "__main__":
    enrich_stop_times()
