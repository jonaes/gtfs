# Creates feed_info.txt
# with dynamic data for start_date and end_date and version
# and static data for the other fields
#



import pandas as pd
from datetime import datetime, timedelta

CALENDAR_DATES_FILE = "calendar_dates.txt"
OUTPUT_FILE = "feed_info.txt"

def generate_feed_info():
    print(f"📂 Lade {CALENDAR_DATES_FILE} ...")
    df = pd.read_csv(CALENDAR_DATES_FILE)

    #set feed validity
    start_date = datetime.now().strftime("%Y%m%d")                                         #start: today 
    last_date = pd.to_datetime(df["date"].astype(str), format="%Y%m%d").max()
    end_date = (last_date + timedelta(days=120)).strftime("%Y%m%d")                        #end: last trip plus 120 days
    version_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

    info = pd.DataFrame([{
        "feed_publisher_name": "No official feed",
        "feed_publisher_url": "https://github.com/jonaes/gtfs/",
        "feed_lang": "de",
        "feed_start_date": start_date,
        "feed_end_date": end_date,
        "feed_version": version_stamp,
        "feed_contact_email": ""
    }])

    info.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ {OUTPUT_FILE} erstellt mit Version {version_stamp}")

if __name__ == "__main__":
    generate_feed_info()



