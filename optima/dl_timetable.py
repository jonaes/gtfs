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
    """
    Rechnet Abfahrts- und Ankunfts-Zeitstempel (dd.mm.yyyy HH:MM) in eine GTFS-konforme
    arrival_time mit Tagessprung um (z. B. 57:50:00), nur basierend auf der Ankunftsuhrzeit
    und dem Offset der Tage zwischen Abfahrt und Ankunft.
    """
    fmt = "%d.%m.%Y %H:%M"
    dep = datetime.strptime(dep_str, fmt)
    arr = datetime.strptime(arr_str, fmt)

    ah = arr.hour
    am = arr.minute

    tage_diff = (arr.date() - dep.date()).days
    total_hours = tage_diff * 24 + ah
    return f"{total_hours:02}:{am:02}:00"

def _extract_richtung(block):
    """
    Die neue Seite hat keinen <h5> mehr im Block-Header.
    - Alt:  block.select_one("h5")
    - Neu:  block.select_one(".card-header > div") -> erster Textstring ist die Richtung
    Fallbacks sind eingebaut, damit der Parser robust bleibt.
    """
    # 1) alter Selektor (falls irgendwann wieder vorhanden)
    h5 = block.select_one("h5")
    if h5 and h5.get_text(strip=True):
        return h5.get_text(strip=True)

    # 2) neuer Selektor
    header_div = block.select_one(".card-header > div")
    if header_div:
        strings = list(header_div.stripped_strings)
        if strings:
            # erster String ist "Villach - Edirne" bzw. "Edirne - Villach"
            return strings[0]

    # 3) Fallback: nichts gefunden
    return None

def parse_timetable(html):
    soup = BeautifulSoup(html, "html.parser")
    grouped = defaultdict(list)

    # jeder Fahrplan-Block (Richtung)
    for block in soup.select(".card.fp-card"):
        richtung = _extract_richtung(block)
        if not richtung:
            continue

        # einzelne Fahrten als Kacheln mit data-Attributen
        for trip in block.select(".calc-day"):
            dep_str = trip.get("data-dep")  # z. B. "26.04.2025 21:32"
            arr_str = trip.get("data-arr")
            if not dep_str or not arr_str:
                continue

            try:
                dep_date, dep_time = dep_str.split()
            except ValueError:
                # falls Format abweicht, Fahrt überspringen
                continue

            gtfs_arrival = calculate_gtfs_time(dep_str, arr_str)

            # Gruppierung wie bisher: Richtung + Abfahrtszeit + GTFS-Ankunft
            key = (richtung, dep_time, gtfs_arrival)
            grouped[key].append(dep_date)

    # Strukturiertes Ergebnis bauen (gleiches Schema wie zuvor)
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

    # Debug-Ausgabe wie gehabt
    for entry in grouped_fahrten:
        print(f"🧭 {entry['richtung']}")
        print(f"   🕒 Abfahrt: {entry['abfahrt_uhrzeit']} → GTFS-Ankunft: {entry['gtfs_arrival']}")
        print(f"   🗓️ Verkehrstage ({len(entry['verkehrstage'])}): {', '.join(entry['verkehrstage'])}\n")

if __name__ == "__main__":
    main()
