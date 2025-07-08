import xml.etree.ElementTree as ET
import pandas as pd
from geopy.distance import geodesic

SHAPE_FILES = {
    "EDIRNE": "shape_edirne.gpx",
    "VILLACH": "shape_villach.gpx"
}
SHAPES_TXT = "shapes.txt"
TRIPS_FILE = "trips.txt"

def parse_gpx(file_path, shape_id):
    print(f"📂 Lese GPX: {file_path} → shape_id={shape_id}")
    ns = {"default": "http://www.topografix.com/GPX/1/1"}
    tree = ET.parse(file_path)
    root = tree.getroot()

    shape_data = []
    sequence = 0
    distance = 0.0
    prev = None

    for trk in root.findall("default:trk", ns):
        for trkseg in trk.findall("default:trkseg", ns):
            for pt in trkseg.findall("default:trkpt", ns):
                lat = float(pt.attrib["lat"])
                lon = float(pt.attrib["lon"])
                if prev:
                    distance += geodesic(prev, (lat, lon)).km
                shape_data.append({
                    "shape_id": shape_id,
                    "shape_pt_lat": lat,
                    "shape_pt_lon": lon,
                    "shape_pt_sequence": sequence,
                    "shape_dist_traveled": round(distance, 6)
                })
                prev = (lat, lon)
                sequence += 1

    print(f"✅ {len(shape_data)} Punkte für {shape_id}")
    return shape_data

def generate_shapes():
    all_shapes = []
    for shape_id, file in SHAPE_FILES.items():
        shape_points = parse_gpx(file, shape_id)
        all_shapes.extend(shape_points)

    df = pd.DataFrame(all_shapes)
    df.to_csv(SHAPES_TXT, index=False)
    print(f"\n💾 shapes.txt geschrieben mit {len(df)} Punkten")

def assign_shape_ids_to_trips():
    df = pd.read_csv(TRIPS_FILE)
    print("\n🔗 Weise shape_id basierend auf trip_headsign zu …")

    def get_shape_id(headsign):
        target = headsign.strip().upper()
        if "EDIRNE" in target:
            return "EDIRNE"
        elif "VILLACH" in target:
            return "VILLACH"
        else:
            raise ValueError(f"⚠️ Kein shape_id-Zuordnung möglich für headsign: {headsign}")

    df["shape_id"] = df["trip_headsign"].apply(get_shape_id)
    df.to_csv(TRIPS_FILE, index=False)
    print(f"✅ trips.txt aktualisiert mit shape_id")

def main():
    generate_shapes()
    assign_shape_ids_to_trips()

if __name__ == "__main__":
    main()
