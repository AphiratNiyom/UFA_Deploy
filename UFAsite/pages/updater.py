from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


class Updater:
    """
    คลาสสำหรับจัดการ Background Scheduler ดึงข้อมูลระดับน้ำอัตโนมัติ
    """
    _scheduler = None

    @classmethod
    def start(cls):
        if cls._scheduler is not None and cls._scheduler.running:
            return

        cls._scheduler = BackgroundScheduler()

        # รันเจาะจงนาที (Cron Trigger)
        # เว็บต้นทางอัพเดทข้อมูลทุก 15 นาที (ที่นาที 00, 15, 30, 45)
        # ตั้งให้ดึงตอนนาทีที่ 02, 17, 32, 47 (เผื่อเวลาดีเลย์ให้ต้นทาง 2 นาที)
        cls._scheduler.add_job(cls.update_water_data, 'cron', minute='2,17,32,47')
        cls._scheduler.start()
        try:
            print("✅ Background Scheduler started successfully (ตั้งเวลา: นาทีที่ 2, 17, 32, 47)")
        except UnicodeEncodeError:
            print("[OK] Background Scheduler started successfully (Cron: min 2, 17, 32, 47)")

    @staticmethod
    def update_water_data():
        try:
            try:
                print("⏰ Scheduler: กำลังเริ่มดึงข้อมูลระดับน้ำอัตโนมัติ...")
            except UnicodeEncodeError:
                print("[INFO] Scheduler: Starting water data scraping...")
            call_command('scrape_data')
            try:
                print("✅ Scheduler: ดึงข้อมูลเสร็จสิ้น")
            except UnicodeEncodeError:
                print("[OK] Scheduler: Data scraping completed")
        except Exception as e:
            try:
                print(f"❌ Scheduler Error: {e}")
            except UnicodeEncodeError:
                print(f"[ERROR] Scheduler Error: {e}")
