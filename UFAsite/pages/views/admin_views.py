from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
import json
import os
import sys
import time
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
        'label': 'ทดสอบและประเมินโมเดล AI',
        'description': 'ทดสอบประสิทธิภาพโมเดล ML (R², MAE, K-Fold) และจำลองสถานการณ์ความเสี่ยงน้ำท่วม',
        'icon': '📊',
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

# เก็บ Process ที่กำลังรันอยู่: {task_id: {'proc': Popen, 'command': str, 'cancelled': bool}}
ACTIVE_COMMAND_PROCESSES = {}


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
    def _kill_proc(proc):
        """ยุติการทำงานของ Process และ Subprocesses ทั้งหมดอย่างปลอดภัย"""
        if not proc or proc.poll() is not None:
            return
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                    capture_output=True,
                    check=False
                )
            else:
                proc.terminate()
                time.sleep(0.3)
                if proc.poll() is None:
                    proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    @staticmethod
    @admin_required
    @require_POST
    def admin_run_command(request):
        """รัน Django management command แบบควบคุมการยกเลิกได้"""
        command_name = request.POST.get('command')
        task_id = request.POST.get('task_id') or f"{command_name}_{int(time.time() * 1000)}"

        if command_name not in ADMIN_COMMANDS:
            return JsonResponse({'success': False, 'output': 'คำสั่งไม่ถูกต้อง', 'cancelled': False})

        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')
        try:
            cmd_args = [sys.executable, manage_py, command_name]

            # แนบ Parameter สำหรับ import_historical_data
            if command_name == 'import_historical_data':
                station_id = request.POST.get('station_id')
                station_code = request.POST.get('api_id')
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')

                if not all([station_id, station_code, start_date, end_date]):
                    return JsonResponse({'success': False, 'output': 'กรุณากรอกข้อมูลให้ครบถ้วน', 'cancelled': False})

                cmd_args.extend([
                    '--station_id', station_id,
                    '--station_code', station_code,
                    '--start', start_date,
                    '--end', end_date
                ])
            elif command_name == 'simulation':
                mode = request.POST.get('mode', 'evaluate')
                if mode in ['evaluate', 'flash_flood', 'backwater', 'simulate']:
                    cmd_args.extend(['--mode', mode])

                time_filter = request.POST.get('time_filter', 'all')
                if time_filter == 'year':
                    sim_year = request.POST.get('sim_year')
                    if sim_year and sim_year != 'all':
                        cmd_args.extend(['--year', sim_year])
                elif time_filter == 'month':
                    sim_year = request.POST.get('sim_year')
                    sim_month = request.POST.get('sim_month')
                    if sim_year and sim_year != 'all':
                        cmd_args.extend(['--year', sim_year])
                    if sim_month and sim_month != 'all':
                        cmd_args.extend(['--month', sim_month])
                elif time_filter == 'custom':
                    start_date = request.POST.get('sim_start_date')
                    end_date = request.POST.get('sim_end_date')
                    if start_date and end_date:
                        cmd_args.extend(['--start', start_date, '--end', end_date])

            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            )

            ACTIVE_COMMAND_PROCESSES[task_id] = {
                'proc': proc,
                'command': command_name,
                'cancelled': False,
                'start_time': time.time(),
            }

            try:
                stdout, stderr = proc.communicate(timeout=120)
                output = stdout or ''
                if stderr:
                    output += '\n[STDERR]\n' + stderr
            except subprocess.TimeoutExpired:
                AdminViews._kill_proc(proc)
                output = 'หมดเวลา (timeout 120 วินาที) — คำสั่งใช้เวลาประมวลผลนานเกินกำหนด กรุณารันผ่าน Terminal/CLI โดยตรง'
                return JsonResponse({'success': False, 'output': output, 'cancelled': False})

            task_info = ACTIVE_COMMAND_PROCESSES.get(task_id, {})
            was_cancelled = task_info.get('cancelled', False)
            success = (proc.returncode == 0) and not was_cancelled

            if was_cancelled:
                output = (output + '\n\n🛑 คำสั่งถูกยกเลิกเรียบร้อยแล้ว (Process Terminated)').strip()

            chart_url = None
            chart_data = None
            if command_name == 'simulation' and success:
                chart_file = os.path.join(settings.BASE_DIR, 'static', 'images', 'evaluation_plot.png')
                if os.path.exists(chart_file):
                    chart_url = f'/static/images/evaluation_plot.png?v={int(time.time())}'

                data_file = os.path.join(settings.BASE_DIR, 'static', 'images', 'evaluation_data.json')
                if os.path.exists(data_file):
                    try:
                        with open(data_file, 'r', encoding='utf-8') as f_json:
                            chart_data = json.load(f_json)
                    except Exception:
                        chart_data = None

            return JsonResponse({
                'success': success,
                'output': output.strip(),
                'cancelled': was_cancelled,
                'chart_url': chart_url,
                'chart_data': chart_data
            })

        except Exception as e:
            return JsonResponse({'success': False, 'output': f'เกิดข้อผิดพลาด: {str(e)}', 'cancelled': False})
        finally:
            ACTIVE_COMMAND_PROCESSES.pop(task_id, None)

    @staticmethod
    @admin_required
    @require_POST
    def admin_cancel_command(request):
        """ยกเลิกคำสั่งที่กำลังทำงานอยู่"""
        task_id = request.POST.get('task_id')
        command_name = request.POST.get('command')

        target_info = None
        target_key = None

        if task_id and task_id in ACTIVE_COMMAND_PROCESSES:
            target_key = task_id
            target_info = ACTIVE_COMMAND_PROCESSES[task_id]
        elif command_name:
            for k, info in list(ACTIVE_COMMAND_PROCESSES.items()):
                if info.get('command') == command_name:
                    target_key = k
                    target_info = info
                    break

        if not target_info:
            return JsonResponse({
                'success': True,
                'message': 'ไม่พบคำสั่งที่กำลังทำงานอยู่ (คำสั่งอาจเสร็จสิ้นหรือถูกยกเลิกไปแล้ว)'
            })

        target_info['cancelled'] = True
        proc = target_info.get('proc')
        AdminViews._kill_proc(proc)

        return JsonResponse({
            'success': True,
            'message': 'ส่งสัญญาณยุติคำสั่งเรียบร้อยแล้ว'
        })
