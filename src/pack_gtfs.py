import zipfile
import os

# Alle GTFS-komponenten, die im ZIP enthalten sein sollen
GTFS_FILES = [
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar_dates.txt",
    "shapes.txt",
    "feed_info.txt"
]

ZIP_NAME = "optima_gtfs.zip"

def build_zip():
    print(f"📦 Erzeuge {ZIP_NAME} ...")

    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fname in GTFS_FILES:
            if os.path.exists(fname):
                zipf.write(fname)
                print(f"  ➕ {fname}")
            else:
                print(f"  ⚠️ Datei fehlt: {fname} (wird übersprungen)")

    print(f"✅ ZIP-Datei erstellt: {ZIP_NAME}")

if __name__ == "__main__":
    build_zip()
