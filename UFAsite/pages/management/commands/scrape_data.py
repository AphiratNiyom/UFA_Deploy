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

class Command(BaseCommand):
    help = 'Scrapes real water level data directly from hidden input tags in the AJAX response.'

    # กำหนดรายชื่อสถานีที่ต้องการดึงข้อมูล
    STATIONS = [
        {
            'station_si': 16,
            'station_id': 'TS16',
            'station_name': 'สถานี TS16 แม่น้ำมูล เมืองอุบลราชธานี (M.7)'
        },
        
        {
             'station_si': 2,
             'station_id': 'TS2',
             'station_name': 'สถานี TS2 แม่น้ำมูล อ.ราษีไศล (M.5) จ.ศรีสะเกษ'
        },

        {
             'station_si': 5,
             'station_id': 'TS5',
             'station_name': 'สถานีTS5 แม่น้ำมูล ท้ายแก่งสะพือ (M.11B) จ.อุบลราชธานี'
        },
    ]

    def handle(self, *args, **kwargs):
        """ดึงข้อมูลจากทุกสถานี"""
        for station_config in self.STATIONS:
            self.scrape_station(station_config)

    def scrape_station(self, station_config):
        """ดึงข้อมูลจากสถานีเดียว"""
        station_si = station_config['station_si']
        station_id = station_config['station_id']
        station_name = station_config['station_name']
        
        # URL ที่ JavaScript ใช้ดึงข้อมูล
        ajax_url = f'https://watertele.egat.co.th/srdpm/dataStation/ajx_teledata_right.php?stationSI={station_si}'

        self.stdout.write(f'Scraping data from hidden inputs for {station_name}...')

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html, */*; q=0.01',
                'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://watertele.egat.co.th/',
                'X-Requested-With': 'XMLHttpRequest',
                'Connection': 'keep-alive',
            }
            # verify=False help avoid SSL errors from some legacy gov servers
            # timeout increased to 30s
            response = requests.get(ajax_url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            response.encoding = 'windows-874'
            soup = BeautifulSoup(response.text, 'html.parser')

            # ดึงข้อมูลจาก <input type="hidden"> โดยตรง
            # 1. ค้นหาระดับน้ำจาก <input id="waterLV">
            water_level_input = soup.find('input', {'id': 'waterLV'})
            if not water_level_input or 'value' not in water_level_input.attrs:
                raise ValueError("Could not find the hidden input tag with id='waterLV'.")
            
            water_level = float(water_level_input['value'])

            # 2. ค้นหาวันที่/เวลาจาก <input id="date">
            date_input = soup.find('input', {'id': 'date'})
            if not date_input or 'value' not in date_input.attrs:
                raise ValueError("Could not find the hidden input tag with id='date'.")

            datetime_str = date_input['value'] # จะได้ '18-09-2568 23:00:00'
            
            # แปลง พ.ศ. เป็น ค.ศ.
            date_part, time_part = datetime_str.split(' ')
            day, month, year_be = date_part.split('-')
            year_ad = int(year_be) - 543
            
            naive_time = datetime.strptime(f"{day}-{month}-{year_ad} {time_part}", '%d-%m-%Y %H:%M:%S')
            recorded_time = make_aware(naive_time)

            # ประเมินความเสี่ยงน้ำท่วม
            risk_level, risk_text = evaluate_flood_risk(water_level, station_id=station_id)
            self.stdout.write(f"Analyzed Risk: {risk_text} (Level: {water_level}m)")

            # บันทึกข้อมูลลง DATABASE
            station, created = WaterStations.objects.get_or_create(
                station_id=station_id,
                defaults={'station_name': station_name}
            )
            
            WaterLevels.objects.create(
                station=station,
                water_level=water_level,
                recorded_at=recorded_time,
                risk_level=risk_level
            )

            # ส่งแจ้งเตือนถ้าระดับน้ำเกินเกณฑ์ (เฉพาะสถานี TS16)
            if risk_level > 0 and station_id == 'TS16' :
                
                # แปลงเวลาเป็น String(เวลาไทย)
                time_str = recorded_time.strftime('%H:%M')
                date_str = recorded_time.strftime('%d/%m/%Y')

                # เลือก Icon ตามความรุนแรง
                icon = "🟡" if risk_level == 1 else "🔴"
                
                # สร้างข้อความแจ้งเตือน
                alert_msg = (
                    f"{icon} แจ้งเตือนความเสี่ยงน้ำท่วม! {icon}\n"
                    f"📍 {station_name}\n"
                    f"🌊 ระดับน้ำ: {water_level} ม.\n"
                    f"📢 สถานะ: {risk_text}\n"
                    f"⏰ เวลา: {time_str} น. ({date_str})"
                )

                # ส่งเข้า Line ทันที (เฉพาะคนที่ is_active=1)
                send_multicast_alert(alert_msg)

            self.stdout.write(self.style.SUCCESS(f'Saved: {water_level}m ({risk_text}) for {station_name}'))

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Could not retrieve the webpage for {station_name}: {e}'))
        except (ValueError, AttributeError, KeyError) as e:
            self.stdout.write(self.style.ERROR(f'Could not parse the page content for {station_name}: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing {station_name}: {e}'))