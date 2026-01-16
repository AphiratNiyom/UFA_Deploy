from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import logging
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