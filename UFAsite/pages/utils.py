# pages/utils.py

from django.conf import settings
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MulticastRequest,
    TextMessage
)
from .models import Users

def send_multicast_alert(message_text):
    """
    ฟังก์ชันสำหรับส่งข้อความหา User ทุกคนที่มีสถานะ is_active = 1
    """
    # 1. ดึง ID ของ User ที่ Active
    user_ids = list(Users.objects.filter(is_active=1).values_list('line_user_id', flat=True))

    if not user_ids:
        print("🔕 No active subscribers found.")
        return

    # 2. ตั้งค่า Line API Client
    configuration = Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            # 3. ส่งข้อความแบบ Multicast
            # ต้องส่งเป็น MulticastRequest
            line_bot_api.multicast(
                MulticastRequest(
                    to=user_ids,
                    messages=[TextMessage(text=message_text)]
                )
            )
            print(f"✅ Sent alert to {len(user_ids)} users.")
            
    except Exception as e:
        print(f"❌ Error sending multicast: {e}")

def get_emergency_flex_message():
    """
    สร้าง Flex Message สำหรับเบอร์โทรฉุกเฉิน
    """
    return {
      "type": "bubble",
      "header": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "📞 เบอร์ฉุกเฉิน (อุบลฯ)",
            "weight": "bold",
            "size": "xl",
            "color": "#FFFFFF"
          }
        ],
        "backgroundColor": "#DC3545",
        "paddingAll": "20px"
      },
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "กดที่ปุ่มเพื่อโทรออกทันที",
            "size": "xs",
            "color": "#aaaaaa",
            "align": "center",
            "margin": "md"
          },
          {
            "type": "separator",
            "margin": "lg"
          },
          {
            "type": "box",
            "layout": "vertical",
            "margin": "lg",
            "spacing": "sm",
            "contents": [
              {
                "type": "button",
                "style": "primary",
                "action": { "type": "uri", "label": "🚑 เจ็บป่วยฉุกเฉิน (1669)", "uri": "tel:1669" }
              },
              {
                "type": "button",
                "style": "secondary",
                "action": { "type": "uri", "label": "🚨 สายด่วนกู้ภัย (1784)", "uri": "tel:1784" }
              },
              {
                "type": "button",
                "style": "secondary",
                "action": { "type": "uri", "label": "📢 ปภ. อุบลฯ (045-344635)", "uri": "tel:045344635" }
              },
              {
                "type": "button",
                "style": "secondary",
                "action": { "type": "uri", "label": "⚡ การไฟฟ้า (1129)", "uri": "tel:1129" }
              },
              {
                "type": "button",
                "style": "secondary",
                "action": { "type": "uri", "label": "💧 การประปา (1662)", "uri": "tel:1662" }
              },
              {
                "type": "button",
                "style": "secondary",
                "action": { "type": "uri", "label": "📌 เทศบาลนครอุบลฯ (045-245500)", "uri": "tel:045245500" }
              }
            ]
          }
        ]
      }
    }