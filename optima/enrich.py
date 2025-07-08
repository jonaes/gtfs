import pandas as pd

TRIPS_FILE = "trips.txt"
TIMELINE_FILE = "timeline.csv"
OUTPUT_FILE = "stop_times.txt"

def enrich_stop_times():
    trips = pd.read_csv(TRIPS_FILE)
    timeline = pd.read_csv(TIMELINE_FILE)

    all_stop_times = []

    for _, trip in trips.iterrows():
        trip_id = trip["trip_id"]
        headsign = trip["trip_headsign"].strip().upper()
        direction = "E" if "EDIRNE" in headsign else "V"

        timeline_part = timeline[timeline["trip_direction"] == direction].copy()

        for _, row in timeline_part.iterrows():
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

    # Setze timepoint: nur der erste Halt = 1, Rest = 0
    df["timepoint"] = 0
    first_stops = df.sort_values("stop_sequence").groupby("trip_id").first().reset_index()
    for _, row in first_stops.iterrows():
        df.loc[
            (df["trip_id"] == row["trip_id"]) &
            (df["stop_sequence"] == row["stop_sequence"]),
            "timepoint"
        ] = 1

    df.sort_values(by=["trip_id", "stop_sequence"], inplace=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ {OUTPUT_FILE} geschrieben mit {len(df)} Einträgen.")

if __name__ == "__main__":
    enrich_stop_times()
