from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .decorators import admin_required
from .models import WaterStations
import logging
import subprocess
import sys
import os
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction,
    FlexMessage,
    FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from .models import Users, WaterLevels 
from .risk_calculator import STATION_THRESHOLDS
from .predictor import load_and_predict
from pages.utils import get_emergency_flex_message

# แสดงผลหน้าเว็บ
def home_page_view(request):
    # 1. ดึงข้อมูลล่าสุดของแต่ละสถานี (TS2=M.5, TS16=M.7, TS5=M.11B)
    data_m5 = WaterLevels.objects.filter(station__station_id='TS2').order_by('-recorded_at').first()
    data_m7 = WaterLevels.objects.filter(station__station_id='TS16').order_by('-recorded_at').first()
    data_m11b = WaterLevels.objects.filter(station__station_id='TS5').order_by('-recorded_at').first()

    context = {
        'm5': data_m5,      # ต้นน้ำ
        'm7': data_m7,      # กลางน้ำ (จุดโฟกัส)
        'm11b': data_m11b,  # ปลายน้ำ
        'today': timezone.now()
    }
    return render(request, 'home.html', context)


# ฟังก์ชันส่งตัวเลือก (Helper Function)
def get_station_selection_message():
    """
    สร้างข้อความถามผู้ใช้ พร้อมปุ่ม Quick Reply ให้เลือกสถานี
    """
    # รายชื่อสถานีพร้อมรหัสย่อที่เราจะใช้เช็ค
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

def get_latest_water_status(station_code='TS16'):
    try:
        # กำหนด Mapping ระหว่าง "คำที่กด" กับ "Station ID ใน Database"
        # M.5 = TS2 (ศรีสะเกษ)
        # M.7 = TS16 (เมืองอุบล)
        # M.11B = TS5 (ท้ายแก่งสะพือ)
        
        db_station_id = 'TS16' # ค่า Default (เผื่อหาไม่เจอ)
        
        if 'M.5' in station_code:
            db_station_id = 'TS2'
        elif 'M.7' in station_code:
            db_station_id = 'TS16'
        elif 'M.11B' in station_code:
            db_station_id = 'TS5'
        
        # ดึงข้อมูลล่าสุดตาม ID ที่ระบุ
        latest_data = WaterLevels.objects.filter(
            station__station_id=db_station_id
        ).order_by('-recorded_at').first()

        if not latest_data:
            return f"❌ ขออภัย ยังไม่มีข้อมูลของสถานี {station_code} ในระบบครับ"
        
        # 3.ดึงเกณฑ์แจ้งเตือนของสถานีนี้ มาเตรียมไว้
        # ถ้าหาไม่เจอ ให้ใช้ของ TS16 เป็นค่า Default
        thresholds = STATION_THRESHOLDS.get(db_station_id, STATION_THRESHOLDS['TS16'])
        warn_val = thresholds['warn']
        crit_val = thresholds['crit']

        # แปลงรหัสความเสี่ยง
        risk_map = {
            0: "🟢 ปกติ",
            1: "🟡 เฝ้าระวัง",
            2: "🔴 วิกฤต"
        }
        current_risk = risk_map.get(latest_data.risk_level, "ไม่ระบุ")
        time_str = timezone.localtime(latest_data.recorded_at).strftime('%d/%m/%Y %H:%M')

        # สร้างข้อความตอบกลับ
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

# ต่อกับ LINE
configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(channel_secret=settings.LINE_CHANNEL_SECRET)


# Webhook
@csrf_exempt
def webhook(request):
    # --- DEBUG POINT 1: ยืนยันว่า LINE เรียกเข้ามาที่ Webhook ของเรา ---
    print("✅ Webhook received a request!")

    # ตรวจสอบลายเซ็นจาก LINE
    signature = request.META['HTTP_X_LINE_SIGNATURE']
    body = request.body.decode('utf-8')

    # --- DEBUG POINT 2: พิมพ์ข้อมูลทั้งหมดที่ LINE ส่งมาให้ดู ---
    # สำคัญที่สุดในการ Debug
    print(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        # --- DEBUG POINT 3: แจ้งเตือนเมื่อลายเซ็นไม่ถูกต้อง ---
        # (สาเหตุมักจะมาจาก Channel Secret ใน settings.py ผิด)
        print("❌ Invalid signature. Please check your channel secret.")
        return HttpResponseForbidden()
    except Exception as e:
        # --- DEBUG POINT 4: ดักจับ Error อื่นๆ ทั้งหมดที่อาจเกิดขึ้น ---
        # (เช่น Error ที่เกิดในฟังก์ชัน handle_message)
        print(f"❌ An error occurred: {e}")
        # (อาจจะยังไม่ต้อง return error กลับไปก็ได้ เพื่อให้ LINE ไม่พยายามส่งซ้ำ)

    return HttpResponse('OK')


# ตัวจัดการข้อความ
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if event.source.type != 'user':
        return

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        user_id = event.source.user_id
        text = event.message.text.strip()
        reply_token = event.reply_token
        
        reply_text = "" # ตัวแปรสำหรับเก็บข้อความตอบกลับแบบปกติ

        # ---------------------------------------------------
        # CASE 1: สมัคร/ยกเลิก
        # ---------------------------------------------------
        if text == 'รับการแจ้งเตือน':
            user, created = Users.objects.get_or_create(
                line_user_id=user_id,
                defaults={'is_active': True, 'is_admin': False, 'registered_at': timezone.now()}
            )
            if created:
                reply_text = "คุณได้สมัครรับการแจ้งเตือนเรียบร้อยแล้วครับ 😊"
            else:
                if not user.is_active:
                    user.is_active = True
                    user.subscribed_at = timezone.now()
                    user.save()
                    reply_text = "กลับมาสมัครรับการแจ้งเตือนอีกครั้ง ยินดีต้อนรับ 😊"
                else:
                    reply_text = "คุณได้สมัครรับการแจ้งเตือนไว้แล้วครับ"

        elif text == 'ยกเลิกการแจ้งเตือน':
            updated_count = Users.objects.filter(line_user_id=user_id, is_active=True).update(is_active=False)
            if updated_count > 0:
                reply_text = "ยกเลิกการรับข้อมูลเรียบร้อยแล้วครับ"
            else:
                reply_text = "คุณยังไม่ได้สมัครรับการแจ้งเตือนครับ"

        # ---------------------------------------------------
        # CASE 2: ขอเมนูเลือกสถานี
        # ---------------------------------------------------
        # เช็คคำให้ตรงกับที่ตั้งใน Rich Menu
        elif text == 'สถานะน้ำ' or text == 'สถานะน้ำปัจจุบัน' or text == 'ดูระดับน้ำ':
            # เรียกฟังก์ชันสร้างปุ่ม Quick Reply
            message_obj = get_station_selection_message()
            
            # ส่งกลับทันที (เพราะมันเป็น Object ไม่ใช่ Text ธรรมดา)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[message_obj]
                )
            )
            return # จบการทำงานฟังก์ชันนี้เลย ไม่ต้องทำข้างล่างต่อ

        # ---------------------------------------------------
        # CASE 3: ผู้ใช้กดเลือกสถานี
        # ---------------------------------------------------
        elif text.startswith('ดู M.') or text.startswith('ดู เขื่อน'):
            # เรียกฟังก์ชันดึงข้อมูล พร้อมส่งข้อความที่กดไปตัดเช็ค
            reply_text = get_latest_water_status(station_code=text)

        # ---------------------------------------------------
        # CASE 4: คาดการณ์น้ำท่วม
        # ---------------------------------------------------
        elif text == 'คาดการณ์ล่วงหน้า':
            # 1. เรียกฟังก์ชันคาดการณ์
            predicted_wl, risk_level, risk_text = load_and_predict()

            # 2. ตรวจสอบผลลัพธ์
            if predicted_wl is not None:
                # 2.1 ถ้าทำนายสำเร็จ
                reply_text = (
                    f"🔮 ผลการคาดการณ์ระดับน้ำที่ M.7 (เมืองอุบลฯ) ในอีก 6 ชั่วโมงข้างหน้า\n"
                    f"------------------------------\n"
                    f"💧 ระดับน้ำที่คาดการณ์: {predicted_wl:.2f} ม.(รทก.)\n"
                    f"⚠️ สถานะ: {risk_text}\n"
                    f"------------------------------\n"
                    f"ข้อความนี้เป็นการประมวลผลจากแบบจำลองเชิงคณิตศาสตร์ ควรใช้เพื่อการเฝ้าระวังและเตรียมตัวเท่านั้น"
                )
            else:
                # 2.2 ถ้าทำนายไม่สำเร็จ (เช่น ไม่มีไฟล์โมเดล), risk_text จะมีข้อความ Error มา
                reply_text = risk_text

        # ---------------------------------------------------
        # ส่งข้อความตอบกลับ (สำหรับ Case ที่ได้ reply_text)
        # ---------------------------------------------------
        if reply_text:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
            )

        # ---------------------------------------------------
        # CASE 6: ขอข้อมูลติดต่อฉุกเฉิน
        # ---------------------------------------------------
        elif text == 'ข้อมูลติดต่อฉุกเฉิน':
            
            # ดึง JSON ของ Flex Message มา
            flex_json = get_emergency_flex_message()
            
            # แปลงเป็น Object ของ Line SDK
            flex_message = FlexMessage(
                alt_text="เบอร์โทรฉุกเฉิน", # ข้อความที่จะขึ้นแจ้งเตือน (Notification)
                contents=FlexContainer.from_dict(flex_json)
            )
            
            # ส่งกลับหา User
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[flex_message]
                )
            )
            return # จบการทำงาน


# =============================================================================
# ADMIN PANEL VIEWS
# =============================================================================

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


def admin_logout(request):
    """ออกจากระบบ Admin"""
    request.session.flush()
    return redirect('admin_login')


@admin_required
def admin_dashboard(request):
    """Dashboard แสดงภาพรวมสถิติ"""
    from .models import Users, WaterLevels, WaterStations
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


@admin_required
def admin_users(request):
    """รายการผู้ใช้ทั้งหมด"""
    from .models import Users
    search = request.GET.get('search', '')
    users = Users.objects.all().order_by('-registered_at')
    if search:
        users = users.filter(display_name__icontains=search)
    context = {'users': users, 'search': search, 'page': 'users'}
    return render(request, 'admin_panel/users.html', context)


@admin_required
def admin_user_toggle(request, user_id):
    """Toggle is_active หรือ is_admin ของ user"""
    from .models import Users
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


@admin_required
def admin_user_delete(request, user_id):
    """ลบผู้ใช้ออกจากระบบ"""
    from .models import Users
    if request.method == 'POST':
        user = get_object_or_404(Users, user_id=user_id)
        user.delete()
    return redirect('admin_users')


@admin_required
def admin_stations(request):
    """รายการสถานีทั้งหมด"""
    from .models import WaterStations
    stations = WaterStations.objects.all().order_by('station_id')
    context = {'stations': stations, 'page': 'stations'}
    return render(request, 'admin_panel/stations.html', context)


@admin_required
def admin_station_edit(request, station_id):
    """แก้ไขข้อมูลสถานี"""
    from .models import WaterStations
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


@admin_required
def admin_commands(request):
    """หน้ารันคำสั่ง Management Commands"""
    context = {'commands': ADMIN_COMMANDS, 'page': 'commands'}
    return render(request, 'admin_panel/commands.html', context)


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
            api_id = request.POST.get('api_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            if not all([station_id, api_id, start_date, end_date]):
                return JsonResponse({'success': False, 'output': 'กรุณากรอกข้อมูลให้ครบถ้วน (Station ID, API ID, Start Date, End Date)'})
            
            cmd_args.extend([
                '--station_id', station_id,
                '--api_id', api_id,
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