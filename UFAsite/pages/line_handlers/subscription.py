from django.utils import timezone
from pages.models import Users

class SubscriptionHandler:
    @staticmethod
    def handle_subscribe(user_id) -> str:
        user, created = Users.objects.get_or_create(line_user_id=user_id, defaults={'is_active': True, 'is_admin': False, 'registered_at': timezone.now()})
        if created:
            return "คุณได้สมัครรับการแจ้งเตือนเรียบร้อยแล้วครับ 😊"
        else:
            if not user.is_active:
                user.is_active = True
                user.subscribed_at = timezone.now()
                user.save()
                return "กลับมาสมัครรับการแจ้งเตือนอีกครั้ง ยินดีต้อนรับ 😊"
            else:
                return "คุณได้สมัครรับการแจ้งเตือนไว้แล้วครับ"

    @staticmethod
    def handle_unsubscribe(user_id) -> str:
        updated_count = Users.objects.filter(line_user_id=user_id, is_active=True).update(is_active=False)
        if updated_count > 0:
            return "ยกเลิกการรับข้อมูลเรียบร้อยแล้วครับ"
        else:
            return "คุณยังไม่ได้สมัครรับการแจ้งเตือนครับ"
