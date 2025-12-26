from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command

def update_water_data():
    try:
        print("⏰ Scheduler: กำลังเริ่มดึงข้อมูลระดับน้ำอัตโนมัติ...")
        call_command('scrape_data') # เรียก management command scrape_data
        print("✅ Scheduler: ดึงข้อมูลเสร็จสิ้น")
    except Exception as e:
        print(f"❌ Scheduler Error: {e}")

def start():
    scheduler = BackgroundScheduler()

    # รันเจาะจงนาที (Cron Trigger)
    # เว็บต้นทางอัพเดทข้อมูลทุก 15 นาที (ที่นาที 00, 15, 30, 45)
    # ตั้งให้ดึงตอนนาทีที่ 02, 17, 32, 47 (เผื่อเวลาดีเลย์ให้ต้นทาง 2 นาที)
    # หมายเหตุ: ถ้าต้นทางอัพเดทแค่ "รายชั่วโมง" ให้ใช้ minute='2' (คือดึงตอนนาทีที่ 2 ของทุกชั่วโมง)
    scheduler.add_job(update_water_data, 'cron', minute='2,17,32,47')

    scheduler.start()