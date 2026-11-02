import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

api_url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
response = requests.get(api_url, verify=False, timeout=30)
data = response.json()

stations_data = []
if 'data' in data:
    if isinstance(data['data'], list):
        stations_data = data['data']
    elif 'waterlevel_data' in data['data']:
        stations_data = data['data']['waterlevel_data']
elif isinstance(data, list):
    stations_data = data

targets = ['M.7', 'M.5', 'M.11B']
for item in stations_data:
    station_info = item.get('station', {})
    station_code = station_info.get('tele_station_oldcode', '')
    if station_code in targets:
        print(f"Code: {station_code}, API_ID: {item.get('id')}")
