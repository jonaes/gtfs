import xml.etree.ElementTree as ET
import pandas as pd
from geopy.distance import geodesic

# Pfad zur GPX-Datei
gpx_file_path = "oe.gpx"

# GPX-Datei einlesen und parsen
tree = ET.parse(gpx_file_path)
root = tree.getroot()

# GPX-Namespace definieren
ns = {'default': 'http://www.topografix.com/GPX/1/1'}

# GPX-Daten extrahieren
shape_data = []
shape_id = "1"
sequence = 0
distance = 0.0
previous_point = None

for trk in root.findall('default:trk', ns):
    for trkseg in trk.findall('default:trkseg', ns):
        for trkpt in trkseg.findall('default:trkpt', ns):
            lat = float(trkpt.attrib['lat'])
            lon = float(trkpt.attrib['lon'])

            if previous_point is not None:
                distance += geodesic(previous_point, (lat, lon)).km

            shape_data.append({
                "shape_id": shape_id,
                "shape_pt_lat": lat,
                "shape_pt_lon": lon,
                "shape_pt_sequence": sequence,
                "shape_dist_traveled": round(distance, 6)
            })

            previous_point = (lat, lon)
            sequence += 1

# In DataFrame umwandeln und als CSV speichern
df = pd.DataFrame(shape_data)
df.to_csv("shapes.txt", index=False)
print("shapes.txt erfolgreich erstellt.")
