import requests
import json

def find_stations():
    potential_urls = [
        "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel",
        "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/tele_waterlevel",
        "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/station",
        "https://api-v3.thaiwater.net/api/v1/thaiwater30/analyst/waterlevel",
    ]

    for url in potential_urls:
        print(f"🔍 Probimg: {url} ...")
        try:
            response = requests.get(url, verify=False, timeout=10)
            if response.status_code == 200:
                print(f"✅ Success! Found valid endpoint: {url}")
                data = response.json()
                
                stations = []
                if 'data' in data:
                    if isinstance(data['data'], list):
                        stations = data['data']
                    elif 'waterlevel_data' in data['data']: # Possible structure
                         stations = data['data']['waterlevel_data']
                elif isinstance(data, list):
                    stations = data
                
                if stations:
                    print(f"   Found {len(stations)} items. Structure of first item:")
                    print(json.dumps(stations[0], indent=2, ensure_ascii=False))

                    print("   Searching for targets...")
                    targets = ['M.7', 'M.5', 'M.11', 'อุบล', 'เสาวภา', 'ราษีไศล', 'แก่งสะพือ']
                    found_count = 0
                    
                    for st in stations:
                        # Extract data from 'station' key based on provided JSON structure
                        station_data = st.get('station', {})
                        name = station_data.get('tele_station_name', {}).get('th', '')
                        # Try 'tele_station_oldcode' first (e.g., M.199), then 'station_code'
                        code = station_data.get('tele_station_oldcode', '') or st.get('station', {}).get('station_code', '')
                        st_id = st.get('id', '') # The ID is at the root level in the example

                        full_text = (name + " " + code).lower()
                        
                        for t in targets:
                            if t.lower() in full_text:
                                print(f"   🎯 เจอแล้ว! ID: {st_id} | Code: {code} | Name: {name}")
                                found_count += 1
                                break
                    
                    if found_count > 0:
                        return # Stop if found
                else:
                    print("   ⚠️  Endpoint returned 200 but no list of data found.")

            else:
                print(f"❌ Failed ({response.status_code})")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    find_stations()
