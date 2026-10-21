
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
  <LOGIN authenticationkey="{escape(API_KEY)}" />
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
    print("Svar fran Trafikverket:")
    print(error.read().decode("utf-8", errors="replace"))
    raise

results = data.get("RESPONSE", {}).get("RESULT", [])
trains = results[0].get("TrainAnnouncement", []) if results else []

report = []

for train in trains:
    products = train.get("ProductInformation") or []
    destinations = train.get("ToLocation") or []

    is_malartag = any(
        "Mälartåg" in str(p.get("Description", ""))
        for p in products
        if isinstance(p, dict)
    )

    to_uppsala = any(
        d.get("LocationName") == "U"
        for d in destinations
        if isinstance(d, dict)
    )

    if not (is_malartag and to_uppsala):
        continue

    report.append({
        "train": train.get("AdvertisedTrainIdent"),
        "departure": train.get("AdvertisedTimeAtLocation"),
        "estimated": train.get("EstimatedTimeAtLocation"),
        "canceled": train.get("Canceled", False),
        "deviation": train.get("Deviation", [])
    })

report.sort(key=lambda x: x.get("departure") or "")

output = {
    "date": today.isoformat(),
    "route": "Tierp till Uppsala",
    "updated": now.isoformat(),
    "trains": report
}

with open("report.json", "w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

print(f"Rapport skapad: {len(report)} avgångar")
