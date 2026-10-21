
import os
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

API_URL = "https://api.trafikinfo.trafikverket.se/v2/data.json"
API_KEY = os.environ["TRAFIKVERKET_API_KEY"]

now = datetime.now(ZoneInfo("Europe/Stockholm"))
today = now.date().isoformat()

query = f"""<REQUEST>
<LOGIN authenticationkey="{API_KEY}"/>
<QUERY objecttype="TrainAnnouncement" schemaversion="1.9">
<FILTER>
<AND>
<EQ name="LocationSignature" value="Tip"/>
<EQ name="ActivityType" value="Avgang"/>
<GTE name="AdvertisedTimeAtLocation" value="{today}T00:00:00"/>
<LT name="AdvertisedTimeAtLocation" value="$dateadd(1.00:00:00,{today}T00:00:00)"/>
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
</REQUEST>"""

request = urllib.request.Request(
    API_URL,
    data=query.encode("utf-8"),
    headers={"Content-Type": "application/xml"},
    method="POST"
)

with urllib.request.urlopen(request, timeout=30) as response:
    data = json.load(response)

trains = data["RESPONSE"]["RESULT"][0]["TrainAnnouncement"]

report = []

for train in trains:
    products = train.get("ProductInformation") or []
    destinations = train.get("ToLocation") or []

    is_malartag = any(
        p.get("Description") == "Mälartåg"
        for p in products
    )
    to_uppsala = any(
        d.get("LocationName") == "U"
        for d in destinations
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

report.sort(key=lambda x: x["departure"])

output = {
    "date": today,
    "route": "Tierp till Uppsala",
    "updated": now.isoformat(),
    "trains": report
}

with open("report.json", "w", encoding="utf-8") as file:
    json.dump(output, file, ensure_ascii=False, indent=2)

print(f"Rapport skapad: {len(report)} avgångar")
