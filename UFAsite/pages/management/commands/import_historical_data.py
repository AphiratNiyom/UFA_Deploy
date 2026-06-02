from django.core.management.base import BaseCommand
import requests
from pages.models import WaterStations, WaterLevels
from django.utils.timezone import make_aware, get_current_timezone
from datetime import datetime, timedelta
import json

class Command(BaseCommand):
    help = 'Imports historical water level data from ThaiWater API'

    def add_arguments(self, parser):
        parser.add_argument('--station_id', type=str, required=True, help='Internal Station ID (e.g., TS16)')
        parser.add_argument('--station_code', type=str, required=True, help='ThaiWater Station Code (e.g., M.7)')
        parser.add_argument('--start', type=str, required=True, help='Start date (YYYY-MM-DD)')
        parser.add_argument('--end', type=str, required=True, help='End date (YYYY-MM-DD)')

    def handle(self, *args, **kwargs):
        station_id = kwargs['station_id']
        station_code = kwargs['station_code']
        start_date_str = kwargs['start']
        end_date_str = kwargs['end']

        # Ensure station exists
        station, created = WaterStations.objects.get_or_create(
            station_id=station_id,
            defaults={'station_name': f'Imported Station {station_code}'}
        )
        if created:
            self.stdout.write(self.style.WARNING(f'Created new station: {station_id}'))

        # Fetch the current numeric API ID for the given station code
        self.stdout.write(f"Looking up numeric API ID for station code: {station_code}")
        try:
            info_url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
            info_resp = requests.get(info_url, verify=False, timeout=30)
            info_resp.raise_for_status()
            info_data = info_resp.json()
            
            stations_data = []
            if 'data' in info_data:
                if isinstance(info_data['data'], list):
                    stations_data = info_data['data']
                elif 'waterlevel_data' in info_data['data']:
                    stations_data = info_data['data']['waterlevel_data']
            elif isinstance(info_data, list):
                stations_data = info_data
                
            api_id = None
            for item in stations_data:
                sc = item.get('station', {}).get('tele_station_oldcode', '')
                if sc == station_code:
                    api_id = str(item.get('station', {}).get('id', ''))
                    break
            
            if not api_id:
                self.stdout.write(self.style.ERROR(f"Could not find numeric API ID for station code: {station_code}"))
                return
                
            self.stdout.write(self.style.SUCCESS(f"Found API ID: {api_id} for {station_code}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching API ID for {station_code}: {e}"))
            return

        # Prepare date chunks (Monthly)
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        current_date = start_date
        total_count = 0
        tz = get_current_timezone()

        while current_date <= end_date:
            # Calculate next month start
            if current_date.month == 12:
                next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                next_month = current_date.replace(month=current_date.month + 1, day=1)
            
            # Determine chunk end date (either end of month or global end date)
            chunk_end_date = next_month - timedelta(days=1)
            if chunk_end_date > end_date:
                chunk_end_date = end_date

            s_str = current_date.strftime('%Y-%m-%d')
            e_str = chunk_end_date.strftime('%Y-%m-%d')
            
            url = f"https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_graph?station_type=tele_waterlevel&station_id={api_id}&start_date={s_str}&end_date={e_str}%2023:59"
            self.stdout.write(f"Fetching: {s_str} to {e_str}")

            try:
                response = requests.get(url, verify=False)
                response.raise_for_status()
                data = response.json()

                if 'data' in data and 'graph_data' in data['data']:
                    graph_data = data['data']['graph_data']
                    for item in graph_data:
                        datetime_str = item['datetime']
                        value = item['value']

                        if value is None:
                            continue

                        try:
                            dt_naive = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            dt_naive = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
                        
                        dt_aware = make_aware(dt_naive, timezone=tz)

                        WaterLevels.objects.update_or_create(
                            station=station,
                            recorded_at=dt_aware,
                            defaults={'water_level': value}
                        )
                        total_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error fetching {s_str}: {e}'))
            
            # Move to next chunk
            current_date = next_month

        self.stdout.write(self.style.SUCCESS(f'Successfully imported {total_count} records for {station_id}'))
