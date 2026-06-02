from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from pages.line_handlers.subscription import SubscriptionHandler
from pages.line_handlers.water_status import WaterStatusHandler
from pages.line_handlers.prediction import PredictionHandler
from pages.line_handlers.emergency import EmergencyHandler

configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(channel_secret=settings.LINE_CHANNEL_SECRET)

@method_decorator(csrf_exempt, name='dispatch')
class LineWebhook(View):
    """จัดการ LINE Webhook และ routing ข้อความจากผู้ใช้ไปยัง handler ต่างๆ"""

    def post(self, request, *args, **kwargs):
        print("✅ Webhook received a request!")
        signature = request.META.get('HTTP_X_LINE_SIGNATURE', '')
        body = request.body.decode('utf-8')
        print(f"Request body: {body}")

        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            print("❌ Invalid signature. Please check your channel secret.")
            return HttpResponseForbidden()
        except Exception as e:
            print(f"❌ An error occurred: {e}")

        return HttpResponse('OK')

    @staticmethod
    @handler.add(MessageEvent, message=TextMessageContent)
    def handle_message(event):
        """ตัวจัดการข้อความที่รับมาจาก LINE"""
        if event.source.type != 'user':
            return

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            user_id = event.source.user_id
            text = event.message.text.strip()
            reply_token = event.reply_token

            reply_text = ""
            messages_to_reply = []

            # ---------------------------------------------------
            # Routing to Handlers
            # ---------------------------------------------------
            if text == 'รับการแจ้งเตือน':
                reply_text = SubscriptionHandler.handle_subscribe(user_id)

            elif text == 'ยกเลิกการแจ้งเตือน':
                reply_text = SubscriptionHandler.handle_unsubscribe(user_id)

            elif text in ['สถานะน้ำ', 'สถานะน้ำปัจจุบัน', 'ดูระดับน้ำ']:
                messages_to_reply.append(WaterStatusHandler.get_station_selection_message())

            elif text.startswith('ดู M.') or text.startswith('ดู เขื่อน'):
                reply_text = WaterStatusHandler.get_latest_water_status(station_code=text)

            elif text == 'คาดการณ์ล่วงหน้า':
                reply_text = PredictionHandler.handle_prediction()

            elif text == 'ข้อมูลติดต่อฉุกเฉิน':
                messages_to_reply.append(EmergencyHandler.get_emergency_flex_message())

            # ---------------------------------------------------
            # Sending Reply
            # ---------------------------------------------------
            if reply_text:
                messages_to_reply.append(TextMessage(text=reply_text))
                
            if messages_to_reply:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=messages_to_reply
                    )
                )
