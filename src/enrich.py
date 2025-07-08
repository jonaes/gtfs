import pandas as pd
from datetime import datetime, timedelta

STOP_TIMES_FILE = "stop_times.txt"
TRIPS_FILE = "trips.txt"
OUTPUT_FILE = "stop_times.txt"  # wird überschrieben

# === Bekannte Zwischenhalte mit Uhrzeiten ===
# Format: (stop_id, "HH:MM" [, "HH:MM"])
HINFAHRT = [
    ("VILLACH", "21:32"),
    ("JESENICE", "22:09", "22:39"),
    ("DOBOVA", "01:20", "01:44"),
    ("TOVARNIK", "07:30", "07:55"),
    ("SID", "08:03", "08:43"),
    ("BEOGRAD", "10:16", "10:20"),
    ("NIS", "15:41", "16:22"),
    ("DIMITROVGRAD", "19:40", "20:10"),
    ("EDIRNE", "06:03")  # Ziel (nächster Tag!)
]

RUECKFAHRT = [
    ("EDIRNE", "17:45"),
    ("DIMITROVGRAD", "03:02", "03:53"),
    ("NIS", "07:08", "07:55"),
    ("BEOGRAD", "12:58", "13:15"),
    ("SID", "15:35", "16:50"),
    ("TOVARNIK", "16:59", "17:29"),
    ("DOBOVA", "23:58", "01:16"),
    ("JESENICE", "05:09", "07:33"),
    ("VILLACH", "08:11")
]

# Hilfsfunktion: Konvertiert "HH:MM" zu Minuten seit Fahrtbeginn
def parse_times(stops):
    timeline = []
    base = datetime.strptime(stops[0][1], "%H:%M")
    for entry in stops:
        sid = entry[0]
        arr = datetime.strptime(entry[1], "%H:%M")
        dep = datetime.strptime(entry[2], "%H:%M") if len(entry) > 2 else arr
        arr_delta = (arr - base).seconds // 60
        dep_delta = (dep - base).seconds // 60
        if arr < base: arr_delta += 1440  # über Mitternacht
        if dep < base: dep_delta += 1440
        timeline.append({
            "stop_id": sid,
            "arrival_offset": arr_delta,
            "departure_offset": dep_delta
        })
    return timeline

def enrich_stop_times():
    print(f"📂 Lese trips.txt ...")
    trips = pd.read_csv(TRIPS_FILE)
    new_rows = []

    for _, row in trips.iterrows():
        tid = row["trip_id"]
        headsign = row["trip_headsign"].upper()

        if "EDIRNE" in headsign:
            timeline = parse_times(HINFAHRT)
        elif "VILLACH" in headsign:
            timeline = parse_times(RUECKFAHRT)
        else:
            print(f"⚠️ Unbekannte Richtung in {tid} – übersprungen")
            continue

        start_time = datetime.strptime("00:00", "%H:%M")

        for i, stop in enumerate(timeline):
            arr = start_time + timedelta(minutes=stop["arrival_offset"])
            dep = start_time + timedelta(minutes=stop["departure_offset"])

            new_rows.append({
                "trip_id": tid,
                "arrival_time": f"{arr.hour + (arr.day - 1) * 24:02}:{arr.minute:02}:00",
                "departure_time": f"{dep.hour + (dep.day - 1) * 24:02}:{dep.minute:02}:00",
                "stop_id": stop["stop_id"],
                "stop_sequence": i + 1,
                "pickup_type": 1,
                "drop_off_type": 1
            })

    df = pd.DataFrame(new_rows)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ {OUTPUT_FILE} neu erzeugt mit {len(df)} Einträgen")

# === Bestehende Timepoint-Postprocessing-Logik ===
def postprocess_timepoints():
    print(f"📂 Nachbearbeitung: Setze timepoint ...")
    df = pd.read_csv(STOP_TIMES_FILE)
    df["timepoint"] = 0
    first_stops = df.sort_values("stop_sequence").groupby("trip_id").first().reset_index()
    for _, row in first_stops.iterrows():
        df.loc[(df["trip_id"] == row["trip_id"]) & (df["stop_sequence"] == row["stop_sequence"]), "timepoint"] = 1
    df.to_csv(STOP_TIMES_FILE, index=False)
    print(f"✅ timepoint-Spalte hinzugefügt")

if __name__ == "__main__":
    enrich_stop_times()
    postprocess_timepoints()
