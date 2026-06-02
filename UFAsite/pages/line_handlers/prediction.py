from pages.predictor import Predictor

class PredictionHandler:
    @staticmethod
    def handle_prediction():
        predicted_wl, risk_level, risk_text = Predictor.load_and_predict()

        if predicted_wl is not None:
            # ถ้าทำนายสำเร็จ
            reply_text = (
                f"🔮 ผลการคาดการณ์ระดับน้ำที่ M.7 (เมืองอุบลฯ) ในอีก 6 ชั่วโมงข้างหน้า\n"
                f"------------------------------\n"
                f"💧 ระดับน้ำที่คาดการณ์: {predicted_wl:.2f} ม.(รทก.)\n"
                f"⚠️ สถานะ: {risk_text}\n"
                f"------------------------------\n"
                f"ข้อความนี้เป็นการประมวลผลจากแบบจำลองเชิงคณิตศาสตร์ ควรใช้เพื่อการเฝ้าระวังและเตรียมตัวเท่านั้น"
            )
        else:
            # ถ้าทำนายไม่สำเร็จ (เช่น ไม่มีไฟล์โมเดล), risk_text จะมีข้อความ Error มา
            reply_text = risk_text

        return reply_text
