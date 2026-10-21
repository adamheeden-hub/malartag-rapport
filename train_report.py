
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
API_KEY = os.environ["TRAFIKVERKET_API_KEY"]

now = datetime.now(ZoneInfo("Europe/Stockholm"))
today = now.date()
tomorrow = today + timedelta(days=1)

start = f"{today.isoformat()}T00:00:00"
end = f"{tomorrow.isoformat()}T00:00:00"

query = f"""
<REQUEST>
  <LOGIN authenticationkey="{escape(API_KEY, {'"': '&quot;'})}" />
  <QUERY objecttype="TrainAnnouncement" schemaversion="1.9">
    <FILTER>
      <AND>
        <EQ name="LocationSignature" value="Tip" />
        <EQ name="ActivityType" value="Avgang" />
        <GTE name="AdvertisedTimeAtLocation" value="{start}" />
        <LT name="AdvertisedTimeAtLocation" value="{end}" />
      </AND>
    </FILTER>
    <INCLUDE>AdvertisedTrainIdent</INCLUDE>
    <INCLUDE>AdvertisedTimeAtLocation</INCLUDE>
    <INCLUDE>EstimatedTimeAtLocation</INCLUDE>
    <INCLUDE>ToLocation</INCLUDE>
    <INCLUDE>Canceled</INCLUDE>
    <INCLUDE>ProductInformation</INCLUDE>
    <INCLUDE>Deviation</INCLUDE>
  </QUERY>
</REQUEST>
"""

request = urllib.request.Request(
    API_URL,
    data=query.encode("utf-8"),
    headers={"Content-Type": "application/xml"},
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
except urllib.error.HTTPError as error:
    print("HTTP-status:", error.code)
    print(error.read().decode("utf-8", errors="replace"))
    raise

results = data.get("RESPONSE", {}).get("RESULT", [])
trains = results[0].get("TrainAnnouncement", []) if results else []

report = []

for train in trains:
    products = train.get("ProductInformation") or []
    destinations = train.get("ToLocation") or []

    is_malartag = any(
        p.get("Description") == "Mälartåg"
        for p in products
        if isinstance(p, dict)
    )

    to_uppsala = any(
        d.get("LocationName") == "U"
        for d in destinations
        if isinstance(d, dict)
    )

    departure = train.get("AdvertisedTimeAtLocation")
    if not departure:
        continue

    departure_time = datetime.fromisoformat(departure)

    if not (
        is_malartag
        and to_uppsala
        and departure_time.strftime("%H:%M") == "06:40"
    ):
        continue

    estimated = train.get("EstimatedTimeAtLocation")
    delay_minutes = None

    if estimated:
        estimated_time = datetime.fromisoformat(estimated)
        delay_minutes = round(
            (estimated_time - departure_time).total_seconds() / 60
        )

    report.append({
        "train": train.get("AdvertisedTrainIdent"),
        "departure": departure,
        "estimated": estimated,
        "delay_minutes": delay_minutes,
        "canceled": train.get("Canceled", False),
        "deviation": train.get("Deviation") or []
    })

output = {
    "date": today.isoformat(),
    "route": "Tierp till Uppsala",
    "scheduled_departure": "06:40",
    "updated": now.isoformat(),
    "trains": report
}

with open("report.json", "w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

if report:
    train = report[0]
    print("Tag:", train["train"])
    print("Avgang:", train["departure"])
    print("Forsening minuter:", train["delay_minutes"])
    print("Installt:", train["canceled"])
else:
    print("Ingen Malartag avgang 06:40 hittades idag")
