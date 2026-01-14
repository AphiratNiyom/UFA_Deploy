import requests
import json

url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_graph?station_type=tele_waterlevel&station_id=2752&start_date=2025-01-01&end_date=2025-01-02"
r = requests.get(url)
data = r.json()
print("Keys in root:", data.keys())
if 'data' in data and 'graph_data' in data['data']:
    graph_data = data['data']['graph_data']
    if graph_data:
        print("First item in graph_data:", graph_data[0])
    else:
        print("graph_data is empty")
else:
    print("Unexpected structure")
