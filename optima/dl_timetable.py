import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from collections import defaultdict
from zoneinfo import ZoneInfo

from gtfs_time import datetime_to_gtfs_minutes, minutes_to_gtfs_time

URL = "https://optimatours.de/timetable"
OUTPUT_JSON = "optima_fahrplan.json"

# GTFS-Zeiten einer Fahrt muessen durchgehend in der agency_timezone angegeben
# werden. Die Optima-Webseite veroeffentlicht dagegen die jeweilige Ortszeit.
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


def calculate_gtfs_times(dep_str, arr_str, direction):
    """
    Rechnet die von Optima gelieferten lokalen Zeitstempel in GTFS-Zeiten um.

    Optima veroeffentlicht Villach in Europe/Vienna und Edirne in
    Europe/Istanbul. GTFS-Time ist verstrichene Zeit seit "noon minus 12h"
    des Verkehrstags in agency_timezone. Dadurch werden sowohl die wechselnde
    Differenz zur Tuerkei als auch Fahrten ueber einen DST-Wechsel korrekt.

    Rueckgabe:
      departure_time (HH:MM, fuer das bestehende JSON-Schema),
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

    # Die Fahrten beginnen nachmittags/abends; damit entspricht das Datum der
    # Abfahrt in agency_timezone eindeutig dem GTFS-Verkehrstag.
    service_date = dep_local.astimezone(AGENCY_TIMEZONE).date()

    dep_minutes = datetime_to_gtfs_minutes(
        dep_local,
        service_date,
        AGENCY_TIMEZONE,
    )
    arr_minutes = datetime_to_gtfs_minutes(
        arr_local,
        service_date,
        AGENCY_TIMEZONE,
    )

    dep_gtfs = minutes_to_gtfs_time(dep_minutes, with_seconds=False)
    arr_gtfs = minutes_to_gtfs_time(arr_minutes, with_seconds=True)

    return dep_gtfs, arr_gtfs, service_date.strftime("%d.%m.%Y")


def _extract_richtung(block):
    """
    Die neue Seite hat keinen <h5> mehr im Block-Header.
    - Alt:  block.select_one("h5")
    - Neu: block.select_one(".card-header > div") -> erster Textstring ist die Richtung
    Fallbacks sind eingebaut, damit der Parser robust bleibt.
    """
    h5 = block.select_one("h5")
    if h5 and h5.get_text(strip=True):
        return h5.get_text(strip=True)

    header_div = block.select_one(".card-header > div")
    if header_div:
        strings = list(header_div.stripped_strings)
        if strings:
            return strings[0]

    return None


def parse_timetable(html):
    soup = BeautifulSoup(html, "html.parser")
    grouped = defaultdict(list)

    for block in soup.select(".card.fp-card"):
        richtung = _extract_richtung(block)
        if not richtung:
            continue

        for trip in block.select(".calc-day"):
            dep_str = trip.get("data-dep")
            arr_str = trip.get("data-arr")
            if not dep_str or not arr_str:
                continue

            try:
                gtfs_departure, gtfs_arrival, service_date = calculate_gtfs_times(
                    dep_str, arr_str, richtung
                )
            except ValueError:
                continue

            # Nach den tatsaechlichen GTFS-Zeiten gruppieren. Eine Fahrt ueber
            # einen DST-Wechsel landet dadurch automatisch in einer eigenen
            # Variante, falls sich ihre verstrichene Gesamtzeit unterscheidet.
            key = (richtung, gtfs_departure, gtfs_arrival)
            grouped[key].append(service_date)

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

    for entry in grouped_fahrten:
        print(f"🧭 {entry['richtung']}")
        print(
            f"   🕒 GTFS ({AGENCY_TIMEZONE.key}): "
            f"{entry['abfahrt_uhrzeit']} → {entry['gtfs_arrival']}"
        )
        print(f"   🗓️ Verkehrstage ({len(entry['verkehrstage'])}): {', '.join(entry['verkehrstage'])}\n")


if __name__ == "__main__":
    main()
