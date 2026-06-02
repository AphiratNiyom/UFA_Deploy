from pages.utils import LineUtils
from linebot.v3.messaging import FlexMessage, FlexContainer

class EmergencyHandler:
    @staticmethod
    def get_emergency_flex_message():
        # ดึง JSON ของ Flex Message มา
        flex_json = LineUtils.get_emergency_flex_message()

        # แปลงเป็น Object ของ Line SDK
        flex_message = FlexMessage(
            alt_text="เบอร์โทรฉุกเฉิน", # ข้อความที่จะขึ้นแจ้งเตือน (Notification)
            contents=FlexContainer.from_dict(flex_json)
        )
        return flex_message
