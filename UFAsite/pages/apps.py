from django.apps import AppConfig

class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'

    def ready(self):
        # เมื่อ Django เริ่มทำงาน ให้ start scheduler ด้วย
        # ต้องเช็คว่าไม่ได้รันอยู่ในโหมด reloader (ป้องกันการรันซ้ำ 2 รอบ)
        import os
        if os.environ.get('RUN_MAIN', None) != 'true' and 'RENDER' not in os.environ:
            return
            
        from . import updater
        updater.start()
        print("🚀 System: Water Scraper Scheduler Started!")