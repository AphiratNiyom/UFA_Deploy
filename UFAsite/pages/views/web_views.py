from django.shortcuts import render
from django.utils import timezone
from pages.models import WaterLevels

class WebViews:
    """Views สำหรับหน้าเว็บสาธารณะ"""

    @staticmethod
    def home_page_view(request):
        # 1. ดึงข้อมูลล่าสุดของแต่ละสถานี (TS2=M.5, TS16=M.7, TS5=M.11B)
        data_m5 = WaterLevels.objects.filter(station__station_id='TS2').order_by('-recorded_at').first()
        data_m7 = WaterLevels.objects.filter(station__station_id='TS16').order_by('-recorded_at').first()
        data_m11b = WaterLevels.objects.filter(station__station_id='TS5').order_by('-recorded_at').first()

        context = {
            'm5': data_m5,
            'm7': data_m7,
            'm11b': data_m11b,
            'today': timezone.now()
        }
        return render(request, 'home.html', context)
