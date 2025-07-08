import pandas as pd
from datetime import datetime

CALENDAR_DATES_FILE = "calendar_dates.txt"
OUTPUT_FILE = "feed_info.txt"

def generate_feed_info():
    print(f"📂 Lade {CALENDAR_DATES_FILE} ...")
    df = pd.read_csv(CALENDAR_DATES_FILE)

    start_date = df["date"].min()
    end_date = df["date"].max()
    version_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    info = pd.DataFrame([{
        "feed_publisher_name": "No official feed",
        "feed_publisher_url": "https://example.com",  # optional anpassen
        "feed_lang": "de",
        "feed_start_date": start_date,
        "feed_end_date": end_date,
        "feed_version": version_stamp,
        "feed_contact_email": "info@example.org"
    }])

    info.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ {OUTPUT_FILE} erstellt mit Version {version_stamp}")

if __name__ == "__main__":
    generate_feed_info()
