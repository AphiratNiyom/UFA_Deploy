import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from django.core.management.base import BaseCommand
from pages.models import WaterStations, WaterLevels
from datetime import datetime
from pages.risk_calculator import RiskCalculator
from django.utils.timezone import make_aware
from pages.utils import LineUtils
import re
from django.utils import timezone


class Command(BaseCommand):
    help = 'Fetches water level data from ThaiWater API and saves to database'

    def handle(self, *args, **kwargs):
        self.stdout.write(timezone.now().strftime('%Y-%m-%d %H:%M:%S'))

        # Mapping: ThaiWater Station Code -> Internal Station ID
        # Using Station Code (M.7, M.5, ...) is more stable than numeric IDs which change often
        STATION_CODE_MAPPING = {
            'M.7': 'TS16',
            'M.5': 'TS2',
            'M.11B': 'TS5',
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
                # Extract station info
                station_info = item.get('station', {})
                station_code = station_info.get('tele_station_oldcode', '')

                # If code matches our target list
                if station_code in STATION_CODE_MAPPING:
                    internal_station_id = STATION_CODE_MAPPING[station_code]

                    water_level_msl = item.get('waterlevel_msl')

                    if water_level_msl is None:
                        self.stdout.write(self.style.WARNING(f"⚠️ Data is None for {internal_station_id} ({station_code})"))
                        continue

                    try:
                        level = float(water_level_msl)
                    except ValueError:
                        self.stdout.write(self.style.ERROR(f"❌ Invalid float value for {internal_station_id}: {water_level_msl}"))
                        continue

                    raw_datetime = item.get('waterlevel_datetime')
                    recorded_at = self.parse_datetime(raw_datetime)

                    self.save_data(internal_station_id, level, recorded_at)
                    found_count += 1

            if found_count > 0:
                self.stdout.write(self.style.SUCCESS(f"✅ Successfully processed {found_count} stations."))
            else:
                self.stdout.write(self.style.WARNING("⚠️ No target stations found in API response."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ API Error: {e}'))

    def parse_datetime(self, dt_str):
        """แปลงข้อความวันที่จาก API เป็น datetime แบบ timezone-aware"""
        if not dt_str:
            return timezone.now()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                naive_dt = datetime.strptime(dt_str.strip(), fmt)
                return make_aware(naive_dt)
            except (ValueError, TypeError):
                continue
        return timezone.now()

    def save_data(self, station_id, level, recorded_at):
        try:
            station = WaterStations.objects.get(station_id=station_id)

            # 1. ป้องกันการบันทึกข้อมูลซ้ำซ้อนเวลาเดียวกัน
            existing_record = WaterLevels.objects.filter(station=station, recorded_at=recorded_at).first()
            if existing_record:
                self.stdout.write(self.style.WARNING(f"⏩ ข้อมูล {station_id} ณ {recorded_at.strftime('%Y-%m-%d %H:%M')} มีอยู่แล้ว (ข้ามการบันทึก)"))
                return

            # ดึงข้อมูลก่อนหน้าเพื่อเปรียบเทียบการแจ้งเตือน (Anti-spam check)
            last_record = WaterLevels.objects.filter(station=station).order_by('-recorded_at').first()

            # 2. คำนวณความเสี่ยง
            risk_level, risk_text = RiskCalculator.evaluate_flood_risk(level, station_id)
            self.stdout.write(f"Analyzed Risk for {station_id}: {risk_text} (Level: {level}m)")

            # 3. บันทึกลงฐานข้อมูล
            WaterLevels.objects.create(
                station=station,
                water_level=level,
                risk_level=risk_level,
                recorded_at=recorded_at,
                data_source='ThaiWater API'
            )
            self.stdout.write(self.style.SUCCESS(f'Saved: {level}m ({risk_text}) for {station.station_name}'))

            # 4. ส่ง LINE Alert เมื่อเข้าสู่วิกฤต (พร้อมกลไกป้องกันการแจ้งเตือนสแปม)
            if risk_level == 2:
                should_alert = False
                alert_reason = ""

                if not last_record or last_record.risk_level != 2:
                    # กรณีที่ 1: เพิ่งเปลี่ยนสถานะเป็นวิกฤต (Transition to Critical)
                    should_alert = True
                    alert_reason = "สถานะเพิ่งเปลี่ยนเป็นวิกฤต"
                else:
                    # กรณีที่ 2: วิกฤตต่อเนื่อง ส่งซ้ำเฉพาะเมื่อผ่านไปแล้วอย่างน้อย 4 ชั่วโมง หรือน้ำขึ้นเพิ่ม >= 0.30 ม.
                    hours_since_last = (timezone.now() - last_record.recorded_at).total_seconds() / 3600 if last_record.recorded_at else 999
                    level_diff = level - float(last_record.water_level) if last_record.water_level else 0

                    if hours_since_last >= 4:
                        should_alert = True
                        alert_reason = f"แจ้งเตือนต่อเนื่องตามรอบ (ผ่านไป {hours_since_last:.1f} ชม.)"
                    elif level_diff >= 0.30:
                        should_alert = True
                        alert_reason = f"ระดับน้ำเพิ่มขึ้นอย่างรวดเร็ว (+{level_diff:.2f} ม.)"

                if should_alert:
                    time_display = timezone.localtime(recorded_at).strftime('%d/%m/%Y %H:%M น.')
                    msg = (
                        f"🚨 แจ้งเตือนน้ำท่วม!\n"
                        f"📍 สถานี: {station.station_name}\n"
                        f"🌊 ระดับน้ำ: {level:.2f} ม.รทก.\n"
                        f"🔥 สถานะ: {risk_text}\n"
                        f"🕒 เวลา: {time_display}"
                    )
                    LineUtils.send_multicast_alert(msg)
                    self.stdout.write(self.style.SUCCESS(f"📢 ส่ง LINE Alert สำหรับ {station.station_name}: {alert_reason}"))
                else:
                    self.stdout.write(self.style.NOTICE(f"ℹ️ ข้ามการส่ง LINE Alert ซ้ำสำหรับ {station.station_name} (สถานะวิกฤตต่อเนื่อง)"))

        except WaterStations.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Station ID {station_id} not found in database'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error saving data for {station_id}: {e}'))
