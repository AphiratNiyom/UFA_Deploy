import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'UFAsite.settings')
django.setup()

from pages.models import WaterLevels

print("Checking WaterLevels for TS16 in 2025...")
total = 0
for m in range(1, 13):
    count = WaterLevels.objects.filter(station__station_id='TS16', recorded_at__year=2025, recorded_at__month=m).count()
    print(f"Month {m}: {count}")
    total += count

print(f"Total 2025: {total}")
