from django.utils import timezone
from linebot.v3.messaging import (
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction
)
from pages.models import WaterLevels
from pages.risk_calculator import RiskCalculator

class WaterStatusHandler:
    @staticmethod
    def get_station_selection_message():
        """
        สร้างข้อความถามผู้ใช้ พร้อมปุ่ม Quick Reply ให้เลือกสถานี
        """
        stations = [
            {"label": "อ.ราษีไศล (M.5)", "text": "ดู M.5"},
            {"label": "เมืองอุบล (M.7)", "text": "ดู M.7"},
            {"label": "ท้ายแก่งสะพือ (M.11B)", "text": "ดู M.11B"}
        ]
        items = []
        for station in stations:
            items.append(
                QuickReplyItem(
                    action=MessageAction(
                        label=station["label"],
                        text=station["text"]
                    )
                )
            )
        return TextMessage(
            text="กรุณาเลือกสถานีที่ต้องการตรวจสอบครับ 👇",
            quick_reply=QuickReply(items=items)
        )

    @staticmethod
    def get_latest_water_status(station_code='TS16'):
        try:
            db_station_id = 'TS16'
            if 'M.5' in station_code:
                db_station_id = 'TS2'
            elif 'M.7' in station_code:
                db_station_id = 'TS16'
            elif 'M.11B' in station_code:
                db_station_id = 'TS5'

            latest_data = WaterLevels.objects.filter(station__station_id=db_station_id).order_by('-recorded_at').first()

            if not latest_data:
                return f"❌ ขออภัย ยังไม่มีข้อมูลของสถานี {station_code} ในระบบครับ"

            thresholds = RiskCalculator.STATION_THRESHOLDS.get(db_station_id, RiskCalculator.STATION_THRESHOLDS['TS16'])
            warn_val = thresholds['warn']
            crit_val = thresholds['crit']

            risk_map = {0: "🟢 ปกติ", 1: "🟡 เฝ้าระวัง", 2: "🔴 วิกฤต"}
            current_risk = risk_map.get(latest_data.risk_level, "ไม่ระบุ")
            time_str = timezone.localtime(latest_data.recorded_at).strftime('%d/%m/%Y %H:%M')

            reply_msg = (
                f"🌊 รายงานสถานการณ์น้ำ\n📍 {latest_data.station.station_name}\n"
                f"🕒 ข้อมูล ณ: {time_str}\n"
                f"------------------------------\n"
                f"💧 ระดับน้ำ: {latest_data.water_level} ม.(รทก.)\n"
                f"⚠️ อยู่ในสถานะ: {current_risk}\n"
                f"------------------------------\n"
                f"📢 เกณฑ์การแจ้งเตือน:\n"
                f"🟡 เฝ้าระวัง: > {warn_val} ม.\n"
                f"🔴 วิกฤต: > {crit_val} ม.\n"
                f"------------------------------\n"
                f"ติดตามสถานการณ์อย่างใกล้ชิดนะครับ ☔"
            )
            return reply_msg

        except Exception as e:
            print(f"Error querying database: {e}")
            return "เกิดข้อผิดพลาดในการดึงข้อมูลชั่วคราวครับ"
