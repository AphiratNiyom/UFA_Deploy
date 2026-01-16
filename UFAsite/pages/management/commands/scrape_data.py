import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from django.core.management.base import BaseCommand
from pages.models import WaterStations, WaterLevels
from datetime import datetime
from pages.risk_calculator import evaluate_flood_risk
from django.utils.timezone import make_aware
from pages.utils import send_multicast_alert
import re
from django.utils import timezone

class Command(BaseCommand):
    help = 'Fetches water level data from ThaiWater API and saves to database'

    def handle(self, *args, **kwargs):
        self.stdout.write(timezone.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Mapping: Internal Station ID -> ThaiWater API Station ID
        # PMTS16 (M.7) = 1192241976
        # PMTS2 (M.5) = 1192234696
        # PMTS5 (M.11B) = 1192241972
        STATION_MAPPING = {
            '1192196943': 'TS16', # M.7 (New ID)
            '1191964977': 'TS2',  # M.5 (New ID)
            '1192196945': 'TS5',  # M.11B (New ID)
        }

        api_url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
        
        try:
            self.stdout.write("🔌 Connecting to ThaiWater API...")
            response = requests.get(api_url, verify=False, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # The API returns a list of stations in 'data' or directly as a list
            stations_data = []
            if 'data' in data:
                if isinstance(data['data'], list):
                    stations_data = data['data']
                elif 'waterlevel_data' in data['data']:
                    stations_data = data['data']['waterlevel_data']
            elif isinstance(data, list):
                stations_data = data

            found_count = 0
            
            for item in stations_data:
                # API structure: item['id'] is the unique ID we found
                tele_id = str(item.get('id', ''))
                
                if tele_id in STATION_MAPPING:
                    station_id = STATION_MAPPING[tele_id]
                    water_level_msl = item.get('waterlevel_msl')
                    
                    if water_level_msl is None:
                        self.stdout.write(self.style.WARNING(f"⚠️ Data is None for {station_id}"))
                        continue

                    try:
                        level = float(water_level_msl)
                    except ValueError:
                        self.stdout.write(self.style.ERROR(f"❌ Invalid float value for {station_id}: {water_level_msl}"))
                        continue

                    self.save_data(station_id, level)
                    found_count += 1
            
            if found_count > 0:
                 self.stdout.write(self.style.SUCCESS(f"✅ Successfully updated {found_count} stations."))
            else:
                 self.stdout.write(self.style.WARNING("⚠️ No target stations found in API response."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ API Error: {e}'))

    def save_data(self, station_id, level):
        try:
            station = WaterStations.objects.get(station_id=station_id)
            
            # Risk Calculation
            risk_level, risk_text = evaluate_flood_risk(level, station_id)
            self.stdout.write(f"Analyzed Risk for {station_id}: {risk_text} (Level: {level}m)")

            # Save to DB
            WaterLevels.objects.create(
                station=station,
                water_level=level,
                risk_level=risk_level,
                recorded_at=timezone.now(),
                data_source='ThaiWater API'
            )
            self.stdout.write(self.style.SUCCESS(f'Saved: {level}m ({risk_text}) for {station.station_name}'))
            
            # Send LINE Alert if Critical
            if risk_level == 2:
                msg = f"🚨 แจ้งเตือนน้ำท่วม!\n📍 สถานี: {station.station_name}\n🌊 ระดับน้ำ: {level} ม.รทก.\n🔥 สถานะ: {risk_text}\n🕒 เวลา: {timezone.now().strftime('%H:%M น.')}"
                send_multicast_alert(msg)

        except WaterStations.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Station ID {station_id} not found in database'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error saving data for {station_id}: {e}'))