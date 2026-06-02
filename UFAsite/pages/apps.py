import os
from django.apps import AppConfig

class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'

    def ready(self):
        # ใช้งานเมื่อไม่ได้ใช้ GitHub Actions
        if os.environ.get('RUN_MAIN', None) != 'true':
            from . import updater
            updater.Updater.start()