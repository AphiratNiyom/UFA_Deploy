import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

api_url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
print(f"Connecting to {api_url}...")

try:
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
        
    print(f"Total stations found: {len(stations_data)}")
    
    target_ids = ['1192241976', '1192234696', '1192241972']
    found = []
    
    for item in stations_data:
        str_id = str(item.get('id', ''))
        name = item.get('station', {}).get('tele_station_name', {}).get('th', '')
        code = item.get('station', {}).get('tele_station_oldcode', '')
        
        if str_id in target_ids:
            found.append(f"FOUND: ID={str_id}, Name={name}, Code={code}, Level={item.get('waterlevel_msl')}")
        
        # Debug: check if maybe the ID changed but name/code matches
        if 'M.7' in code or 'M.5' in code or 'M.11' in code:
             print(f"POTENTIAL MATCH BY CODE: ID={str_id}, Name={name}, Code={code}")

    if found:
        print("\n--- Success Matches ---")
        for f in found:
            print(f)
    else:
        print("\n--- NO DIRECT ID MATCHES ---")

except Exception as e:
    print(f"Error: {e}")
