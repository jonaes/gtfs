import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from collections import defaultdict
from zoneinfo import ZoneInfo

URL = "https://optimatours.de/timetable"
OUTPUT_JSON = "optima_fahrplan.json"

# GTFS-Zeiten einer Fahrt müssen durchgehend in der agency_timezone angegeben
# werden. Die Optima-Webseite veröffentlicht dagegen die jeweilige Ortszeit.
AGENCY_TIMEZONE = ZoneInfo("Europe/Berlin")
STOP_TIMEZONES = {
    "Villach": ZoneInfo("Europe/Vienna"),
    "Edirne": ZoneInfo("Europe/Istanbul"),
}


def fetch_html(url):
    print(f"🔄 Lade HTML von {url} ...")
    resp = requests.get(url)
    resp.raise_for_status()
    print("✅ HTML geladen")
    return resp.text


def _direction_stops(direction):
    stops = [part.strip() for part in direction.split(" - ")]
    if len(stops) != 2 or any(stop not in STOP_TIMEZONES for stop in stops):
        raise ValueError(f"Unbekannte Richtung: {direction!r}")
    return stops[0], stops[1]


def _gtfs_time(dt, service_date, with_seconds=True):
    day_offset = (dt.date() - service_date).days
    if day_offset < 0:
        raise ValueError("Zeit liegt vor dem GTFS-Verkehrstag")

    total_hours = day_offset * 24 + dt.hour
    result = f"{total_hours:02}:{dt.minute:02}"
    return result + ":00" if with_seconds else result


def calculate_gtfs_times(dep_str, arr_str, direction):
    """
    Rechnet die von Optima gelieferten lokalen Zeitstempel in die einheitliche
    GTFS-Agenturzeitzone (Europe/Berlin) um.

    Optima veröffentlicht Villach in Europe/Vienna und Edirne in
    Europe/Istanbul. Dadurch ist die Differenz Edirne <-> Mitteleuropa je nach
    Jahreszeit ein oder zwei Stunden. ZoneInfo berücksichtigt dies anhand des
    konkreten Verkehrstags automatisch.

    Rückgabe:
      departure_time (HH:MM, für das bestehende JSON-Schema),
      arrival_time   (GTFS HH:MM:SS, ggf. > 24 h),
      GTFS-Verkehrstag (dd.mm.yyyy in agency_timezone)
    """
    fmt = "%d.%m.%Y %H:%M"
    from_stop, to_stop = _direction_stops(direction)

    dep_local = datetime.strptime(dep_str, fmt).replace(
        tzinfo=STOP_TIMEZONES[from_stop]
    )
    arr_local = datetime.strptime(arr_str, fmt).replace(
        tzinfo=STOP_TIMEZONES[to_stop]
    )

    dep_agency = dep_local.astimezone(AGENCY_TIMEZONE)
    arr_agency = arr_local.astimezone(AGENCY_TIMEZONE)

    service_date = dep_agency.date()
    dep_gtfs = _gtfs_time(dep_agency, service_date, with_seconds=False)
    arr_gtfs = _gtfs_time(arr_agency, service_date, with_seconds=True)

    return dep_gtfs, arr_gtfs, service_date.strftime("%d.%m.%Y")


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
                gtfs_departure, gtfs_arrival, service_date = calculate_gtfs_times(
                    dep_str, arr_str, richtung
                )
            except ValueError:
                # falls Format oder Richtung abweicht, Fahrt überspringen
                continue

            # Nach den bereits auf agency_timezone normalisierten Zeiten gruppieren.
            # Dadurch werden Sommer-/Wintervarianten mit unterschiedlicher
            # Türkei-Zeitdifferenz automatisch in getrennte GTFS-Trips aufgeteilt.
            key = (richtung, gtfs_departure, gtfs_arrival)
            grouped[key].append(service_date)

    # Strukturiertes Ergebnis bauen (gleiches Schema wie zuvor)
    result = []
    for (richtung, gtfs_departure, gtfs_arrival), dates in grouped.items():
        sorted_dates = sorted(dates, key=lambda d: datetime.strptime(d, "%d.%m.%Y"))
        result.append({
            "richtung": richtung,
            "abfahrt_uhrzeit": gtfs_departure,
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
        print(
            f"   🕒 GTFS ({AGENCY_TIMEZONE.key}): "
            f"{entry['abfahrt_uhrzeit']} → {entry['gtfs_arrival']}"
        )
        print(f"   🗓️ Verkehrstage ({len(entry['verkehrstage'])}): {', '.join(entry['verkehrstage'])}\n")


if __name__ == "__main__":
    main()
