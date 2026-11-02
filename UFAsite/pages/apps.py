import os
import sys
from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'

    def ready(self):
        # ป้องกันไม่ให้ Scheduler เริ่มทำงานในระหว่างคำสั่ง management ทั่วไป เช่น test, migrate, scrape_data
        ignore_commands = {
            'test', 'migrate', 'makemigrations', 'collectstatic',
            'scrape_data', 'train_model', 'simulation', 'inspect_api'
        }
        is_management_cmd = any(cmd in sys.argv for cmd in ignore_commands)

        # ควบคุมผ่าน ENABLE_SCHEDULER (หากใช้ GitHub Actions สามารถปิด scheduler ในเครื่องได้)
        enable_scheduler = os.environ.get('ENABLE_SCHEDULER', 'true').lower() in ('true', '1')

        if enable_scheduler and not is_management_cmd:
            is_runserver = 'runserver' in sys.argv
            # กรณี django runserver ให้รันใน child worker หลัก (RUN_MAIN == 'true')
            # กรณีอื่นๆ เช่น gunicorn ให้รันได้ทันที
            if is_runserver:
                if os.environ.get('RUN_MAIN') == 'true':
                    from . import updater
                    updater.Updater.start()
            elif 'gunicorn' in sys.argv[0] or any('wsgi' in arg for arg in sys.argv):
                from . import updater
                updater.Updater.start()
