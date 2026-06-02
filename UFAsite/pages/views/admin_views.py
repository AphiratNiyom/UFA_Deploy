from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
import os
import sys
import subprocess
from pages.decorators import admin_required

ADMIN_COMMANDS = {
    'scrape_data': {
        'label': 'ดึงข้อมูลจาก API',
        'description': 'ดึงข้อมูลระดับน้ำล่าสุดจาก API กรมชลประทาน บันทึกลงฐานข้อมูล',
        'icon': '🌊',
        'color': 'blue',
    },
    'simulation': {
        'label': 'จำลองน้ำท่วม',
        'description': 'รันโมเดล ML ประเมินความเสี่ยงน้ำท่วมจากข้อมูลปัจจุบัน',
        'icon': '🤖',
        'color': 'purple',
    },
    'train_model': {
        'label': 'เทรนโมเดล ML',
        'description': 'เทรนโมเดลทำนายระดับน้ำใหม่จากข้อมูลประวัติศาสตร์ทั้งหมด',
        'icon': '🧠',
        'color': 'amber',
    },
    'import_historical_data': {
        'label': 'นำเข้าข้อมูลประวัติ',
        'description': 'Import ข้อมูลระดับน้ำย้อนหลังเข้าสู่ฐานข้อมูล',
        'icon': '📂',
        'color': 'green',
    },
}

class AdminViews:
    """Admin Panel Views"""

    @staticmethod
    def admin_login(request):
        """หน้า Login สำหรับ Admin Panel"""
        if request.session.get('is_admin_logged_in'):
            return redirect('admin_dashboard')

        error = None
        if request.method == 'POST':
            password = request.POST.get('password', '')
            if password == settings.ADMIN_PASSWORD:
                request.session['is_admin_logged_in'] = True
                request.session.set_expiry(28800)  # 8 ชั่วโมง
                return redirect('admin_dashboard')
            else:
                error = 'รหัสผ่านไม่ถูกต้อง'

        return render(request, 'admin_panel/login.html', {'error': error})

    @staticmethod
    def admin_logout(request):
        """ออกจากระบบ Admin"""
        request.session.flush()
        return redirect('admin_login')

    @staticmethod
    @admin_required
    def admin_dashboard(request):
        """Dashboard แสดงภาพรวมสถิติ"""
        from pages.models import Users, WaterLevels, WaterStations
        total_users = Users.objects.count()
        active_users = Users.objects.filter(is_active=1).count()
        total_stations = WaterStations.objects.count()
        active_stations = WaterStations.objects.filter(is_active=1).count()
        recent_levels = WaterLevels.objects.select_related('station').order_by('-recorded_at')[:10]

        context = {
            'total_users': total_users,
            'active_users': active_users,
            'total_stations': total_stations,
            'active_stations': active_stations,
            'recent_levels': recent_levels,
            'page': 'dashboard',
        }
        return render(request, 'admin_panel/dashboard.html', context)

    @staticmethod
    @admin_required
    def admin_users(request):
        """รายการผู้ใช้ทั้งหมด"""
        from pages.models import Users
        search = request.GET.get('search', '')
        users = Users.objects.all().order_by('-registered_at')
        if search:
            users = users.filter(display_name__icontains=search)
        context = {'users': users, 'search': search, 'page': 'users'}
        return render(request, 'admin_panel/users.html', context)

    @staticmethod
    @admin_required
    def admin_user_toggle(request, user_id):
        """Toggle is_active หรือ is_admin ของ user"""
        from pages.models import Users
        if request.method == 'POST':
            user = get_object_or_404(Users, user_id=user_id)
            field = request.POST.get('field')
            if field == 'is_active':
                user.is_active = 0 if user.is_active else 1
                user.save()
            elif field == 'is_admin':
                user.is_admin = 0 if user.is_admin else 1
                user.save()
        return redirect('admin_users')

    @staticmethod
    @admin_required
    def admin_user_delete(request, user_id):
        """ลบผู้ใช้ออกจากระบบ"""
        from pages.models import Users
        if request.method == 'POST':
            user = get_object_or_404(Users, user_id=user_id)
            user.delete()
        return redirect('admin_users')

    @staticmethod
    @admin_required
    def admin_stations(request):
        """รายการสถานีทั้งหมด"""
        from pages.models import WaterStations
        stations = WaterStations.objects.all().order_by('station_id')
        context = {'stations': stations, 'page': 'stations'}
        return render(request, 'admin_panel/stations.html', context)

    @staticmethod
    @admin_required
    def admin_station_edit(request, station_id):
        """แก้ไขข้อมูลสถานี"""
        from pages.models import WaterStations
        station = get_object_or_404(WaterStations, station_id=station_id)
        if request.method == 'POST':
            station.warning_level = request.POST.get('warning_level') or None
            station.critical_level = request.POST.get('critical_level') or None
            station.is_active = int(request.POST.get('is_active', 1))
            station.updated_at = timezone.now()
            station.save()
            return redirect('admin_stations')
        context = {'station': station, 'page': 'stations'}
        return render(request, 'admin_panel/station_edit.html', context)

    @staticmethod
    @admin_required
    def admin_commands(request):
        """หน้ารันคำสั่ง Management Commands"""
        context = {'commands': ADMIN_COMMANDS, 'page': 'commands'}
        return render(request, 'admin_panel/commands.html', context)

    @staticmethod
    @admin_required
    @require_POST
    def admin_run_command(request):
        """รัน Django management command และส่ง output กลับ"""
        command_name = request.POST.get('command')
        if command_name not in ADMIN_COMMANDS:
            return JsonResponse({'success': False, 'output': 'คำสั่งไม่ถูกต้อง'})

        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
        try:
            cmd_args = [sys.executable, manage_py, command_name]
            
            # แนบ Parameter สำหรับ import_historical_data
            if command_name == 'import_historical_data':
                station_id = request.POST.get('station_id')
                station_code = request.POST.get('api_id')  # Keeping api_id key from frontend for compatibility
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                
                if not all([station_id, station_code, start_date, end_date]):
                    return JsonResponse({'success': False, 'output': 'กรุณากรอกข้อมูลให้ครบถ้วน'})
                
                cmd_args.extend([
                    '--station_id', station_id,
                    '--station_code', station_code,
                    '--start', start_date,
                    '--end', end_date
                ])

            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=300,  # timeout 5 นาที
                encoding='utf-8',
                errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            )
            output = result.stdout or ''
            if result.stderr:
                output += '\n[STDERR]\n' + result.stderr
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            output = 'หมดเวลา (timeout 5 นาที) — คำสั่งอาจยังทำงานอยู่ใน background'
            success = False
        except Exception as e:
            output = f'เกิดข้อผิดพลาด: {str(e)}'
            success = False

        return JsonResponse({'success': success, 'output': output.strip()})
