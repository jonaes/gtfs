import json
import pandas as pd
from datetime import datetime

# === Pfade zu Ein- und Ausgabedateien ===
INPUT_JSON = "optima_fahrplan.json"
STOPS_FILE = "stops.txt"

ROUTES_FILE = "routes.txt"
TRIPS_FILE = "trips.txt"
CALENDAR_DATES_FILE = "calendar_dates.txt"
STOP_TIMES_FILE = "stop_times.txt"

# === Manuelles Mapping von Richtungsnamen zu stop_id aus stops.txt ===
stop_alias = {
    "Villach": "VILLACH",
    "Edirne": "EDIRNE"
}

# === Lade statische Stopdaten (für Validierung oder spätere Verwendung) ===
def load_stops():
    df = pd.read_csv(STOPS_FILE)
    stop_ids = set(df["stop_id"])
    return stop_ids

# === Lade JSON mit Fahrplanvarianten ===
def load_fahrplan():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

# === routes.txt erzeugen ===
def write_routes():
    df = pd.DataFrame([{
        "route_id": "OPTIMA",
        "agency_id": "OPTIMA",
        "route_short_name": "Optima Express",
        "route_type": 2  # 2 = Bahn
    }])
    df.to_csv(ROUTES_FILE, index=False)
    print(f"✅ {ROUTES_FILE} geschrieben")

# === trips, calendar_dates, stop_times erzeugen ===
def generate_trips_and_times(data):
    trips = []
    calendar = []
    stop_times = []

    for idx, variant in enumerate(data, start=1):
        service_id = f"S{idx}"
        trip_id = f"T{idx}"
        direction = variant["richtung"]
        dep_time = variant["abfahrt_uhrzeit"] + ":00"  # neu: ergänze Sekunden
        arr_time = variant["gtfs_arrival"]

        from_name = direction.split(" - ")[0].strip()
        to_name = direction.split(" - ")[-1].strip()
        from_stop = stop_alias.get(from_name)
        to_stop = stop_alias.get(to_name)

        if not from_stop or not to_stop:
            raise ValueError(f"⚠️ Unbekannter Haltepunkt: '{from_name}' oder '{to_name}' – bitte Alias ergänzen")

        headsign = to_name  # Zielbahnhof als headsign

        print(f"\n🧩 {trip_id} | {direction} | {dep_time} → {arr_time}")
        print(f"   ↪ trip_headsign: {headsign}, service_id: {service_id}")

        # === Trip-Eintrag ===
        trips.append({
            "route_id": "OPTIMA",
            "service_id": service_id,
            "trip_id": trip_id,
            "trip_headsign": headsign
        })

        # === Verkehrstage ===
        for date in variant["verkehrstage"]:
            yyyymmdd = datetime.strptime(date, "%d.%m.%Y").strftime("%Y%m%d")
            calendar.append({
                "service_id": service_id,
                "date": yyyymmdd,
                "exception_type": 1
            })
            print(f"     📅 {yyyymmdd}")

        # === Stop Times ===
        stop_times.append({
            "trip_id": trip_id,
            "arrival_time": dep_time,
            "departure_time": dep_time,
            "stop_id": from_stop,
            "stop_sequence": 1
        })
        stop_times.append({
            "trip_id": trip_id,
            "arrival_time": arr_time,
            "departure_time": arr_time,
            "stop_id": to_stop,
            "stop_sequence": 2
        })

    # CSV schreiben
    pd.DataFrame(trips).to_csv(TRIPS_FILE, index=False)
    pd.DataFrame(calendar).to_csv(CALENDAR_DATES_FILE, index=False)
    pd.DataFrame(stop_times).to_csv(STOP_TIMES_FILE, index=False)

    print(f"\n✅ {TRIPS_FILE} geschrieben ({len(trips)} Fahrten)")
    print(f"✅ {CALENDAR_DATES_FILE} geschrieben ({len(calendar)} Verkehrstage)")
    print(f"✅ {STOP_TIMES_FILE} geschrieben ({len(stop_times)} Stopzeiten)")

# === Hauptfunktion ===
def main():
    load_stops()  # validiert, nicht zwingend verwendet
    data = load_fahrplan()
    write_routes()
    generate_trips_and_times(data)

if __name__ == "__main__":
    main()
