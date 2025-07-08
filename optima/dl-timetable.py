import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from collections import defaultdict

URL = "https://optimatours.de/timetable"
OUTPUT_JSON = "optima_fahrplan.json"

def fetch_html(url):
    print(f"🔄 Lade HTML von {url} ...")
    resp = requests.get(url)
    resp.raise_for_status()
    print("✅ HTML geladen")
    return resp.text

def calculate_gtfs_time(dep_str, arr_str):
    fmt = "%d.%m.%Y %H:%M"
    dep = datetime.strptime(dep_str, fmt)
    arr = datetime.strptime(arr_str, fmt)
    delta = arr - dep
    total_minutes = int(delta.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02}:{minutes:02}:00"

def parse_timetable(html):
    soup = BeautifulSoup(html, "html.parser")
    grouped = defaultdict(list)

    for block in soup.select(".card.fp-card"):
        direction_tag = block.select_one("h5")
        if not direction_tag:
            continue
        richtung = direction_tag.get_text(strip=True)

        for trip in block.select(".calc-day"):
            dep_str = trip.get("data-dep")  # z. B. "26.04.2025 21:32"
            arr_str = trip.get("data-arr")

            dep_date, dep_time = dep_str.split()
            arr_date, arr_time = arr_str.split()
            gtfs_arrival = calculate_gtfs_time(dep_str, arr_str)

            key = (richtung, dep_time, gtfs_arrival)
            grouped[key].append(dep_date)

    # Strukturiertes Ergebnis bauen
    result = []
    for (richtung, dep_time, gtfs_arrival), dates in grouped.items():
        sorted_dates = sorted(dates, key=lambda d: datetime.strptime(d, "%d.%m.%Y"))
        result.append({
            "richtung": richtung,
            "abfahrt_uhrzeit": dep_time,
            "gtfs_arrival": gtfs_arrival,
            "verkehrstage": sorted_dates
        })

    return result

def main():
    html = fetch_html(URL)
    grouped_fahrten = parse_timetable(html)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(grouped_fahrten, f, ensure_ascii=False, indent=2)

    print(f"\n💾 {OUTPUT_JSON} geschrieben mit {len(grouped_fahrten)} Fahrtvarianten\n")

    # Debug-Ausgabe
    for entry in grouped_fahrten:
        print(f"🧭 {entry['richtung']}")
        print(f"   🕒 Abfahrt: {entry['abfahrt_uhrzeit']} → GTFS-Ankunft: {entry['gtfs_arrival']}")
        print(f"   🗓️ Verkehrstage ({len(entry['verkehrstage'])}): {', '.join(entry['verkehrstage'])}\n")

if __name__ == "__main__":
    main()
