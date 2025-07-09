import pandas as pd
import json

TRIPS_FILE = "trips.txt"
TIMELINE_FILE = "timeline.csv"
FAHRPLAN_FILE = "optima_fahrplan.json"
OUTPUT_FILE = "stop_times.txt"

def time_to_minutes(t: str) -> int:
    h, m, *_ = map(int, t.strip().split(":"))
    return h * 60 + m

def minutes_to_gtfs(t: float) -> str:
    total = round(t)
    h, m = divmod(total, 60)
    return f"{int(h):02}:{int(m):02}:00"

def load_fahrplan():
    with open(FAHRPLAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def enrich_stop_times():
    print(f"📥 Lade {TRIPS_FILE}, {TIMELINE_FILE} und {FAHRPLAN_FILE} ...")
    trips = pd.read_csv(TRIPS_FILE)
    timeline = pd.read_csv(TIMELINE_FILE)
    fahrplan = load_fahrplan()

    all_stop_times = []

    for idx, trip in trips.iterrows():
        trip_id = str(trip["trip_id"]).strip()
        headsign = str(trip["trip_headsign"]).strip().upper()
        richtung = "E" if "EDIRNE" in headsign else "V"

        # hole Fahrtinformationen aus Fahrplan (Index-Entsprechung)
        try:
            fahrdaten = fahrplan[idx]
            abfahrt = fahrdaten["abfahrt_uhrzeit"]
            ankunft = fahrdaten["gtfs_arrival"]
        except IndexError:
            raise ValueError(f"❌ Kein Fahrplaneintrag für trip {trip_id} (Index {idx})")

        start_min = time_to_minutes(abfahrt)
        end_min = time_to_minutes(ankunft)
        actual_duration = end_min - start_min
        if actual_duration <= 0:
            raise ValueError(f"❌ Ungültige Zeitspanne für {trip_id}: {abfahrt} → {ankunft}")

        t_section = timeline[timeline["trip_direction"] == richtung].copy()
        t_section.sort_values("stop_sequence", inplace=True)

        ref_start = time_to_minutes(t_section.iloc[0]["departure_time"])
        ref_end = time_to_minutes(t_section.iloc[-1]["arrival_time"])
        ref_duration = ref_end - ref_start

        for _, row in t_section.iterrows():
            for t_type in ["arrival_time", "departure_time"]:
                ref_min = time_to_minutes(row[t_type])
                offset = ref_min - ref_start
                scaled_min = start_min + (offset / ref_duration) * actual_duration
                row[t_type] = minutes_to_gtfs(scaled_min)

            all_stop_times.append({
                "trip_id": trip_id,
                "arrival_time": row["arrival_time"],
                "departure_time": row["departure_time"],
                "stop_id": row["stop_id"],
                "stop_sequence": row["stop_sequence"],
                # Platzhalter – wird unten gesetzt
                "pickup_type": None,
                "drop_off_type": None,
                "timepoint": 0
            })

    df = pd.DataFrame(all_stop_times)
    df.sort_values(["trip_id", "stop_sequence"], inplace=True)

    # Standardmäßig: kein Einstieg/Ausstieg
    df["pickup_type"] = 1
    df["drop_off_type"] = 1

    # Erster Halt je trip_id = Einstieg erlaubt
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
    print(f"✅ {OUTPUT_FILE} geschrieben mit {len(df)} Einträgen.")

if __name__ == "__main__":
    enrich_stop_times()
