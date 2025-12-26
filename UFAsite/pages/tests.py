from django.test import TestCase
from pages.risk_calculator import evaluate_flood_risk

class RiskCalculatorTest(TestCase):
    """
    Test Case สำหรับฟังก์ชัน evaluate_flood_risk (Unit Test)
    ทดสอบ Logic การคำนวณความเสี่ยงแยกจากส่วนอื่น โดยเน้นค่าขอบเขต
    """

    def test_risk_critical(self):
        """
        ทดสอบเกณฑ์วิกฤต (Crisis)
        เงื่อนไข: ระดับน้ำ >= 112.00
        """
        # กรณี 1: เท่ากับ 112 พอดี (Boundary Value) - ต้องเป็นวิกฤต
        level, status = evaluate_flood_risk(112.00)
        self.assertEqual(level, 2, "112.00 ต้องได้ level 2")
        self.assertEqual(status, "วิกฤต (น้ำล้นตลิ่ง)", "112.00 ต้องได้สถานะ 'วิกฤต (น้ำล้นตลิ่ง)'")
        
        # กรณี 2: มากกว่า 112 - ต้องเป็นวิกฤต
        level, status = evaluate_flood_risk(115.50)
        self.assertEqual(level, 2, "115.50 ต้องได้ level 2")
        self.assertEqual(status, "วิกฤต (น้ำล้นตลิ่ง)", "115.50 ต้องได้สถานะ 'วิกฤต (น้ำล้นตลิ่ง)'")

    def test_risk_warning(self):
        """
        ทดสอบเกณฑ์เฝ้าระวัง (Warning)
        เงื่อนไข: 110.00 <= ระดับน้ำ < 112.00
        """
        # กรณี 1: เท่ากับ 110 พอดี (Boundary Value) - ต้องเป็นเฝ้าระวัง
        level, status = evaluate_flood_risk(110.00)
        self.assertEqual(level, 1, "110.00 ต้องได้ level 1")
        self.assertEqual(status, "เฝ้าระวัง", "110.00 ต้องได้สถานะ 'เฝ้าระวัง'")

        # กรณี 2: ค่าระหว่างกลาง (เช่น 111.50) - ต้องเป็นเฝ้าระวัง
        level, status = evaluate_flood_risk(111.50)
        self.assertEqual(level, 1, "111.50 ต้องได้ level 1")
        self.assertEqual(status, "เฝ้าระวัง", "111.50 ต้องได้สถานะ 'เฝ้าระวัง'")

        # กรณี 3: เกือบจะถึง 112 (111.99) - ยังต้องเป็นเฝ้าระวัง (สำคัญ!)
        level, status = evaluate_flood_risk(111.99)
        self.assertEqual(level, 1, "111.99 ต้องได้ level 1")
        self.assertEqual(status, "เฝ้าระวัง", "111.99 ต้องได้สถานะ 'เฝ้าระวัง'")

    def test_risk_normal(self):
        """
        ทดสอบเกณฑ์ปกติ (Normal)
        เงื่อนไข: ระดับน้ำ < 110.00
        """
        # กรณี 1: เกือบจะถึง 110 (109.99) - ต้องเป็นปกติ (สำคัญ!)
        level, status = evaluate_flood_risk(109.99)
        self.assertEqual(level, 0, "109.99 ต้องได้ level 0")
        self.assertEqual(status, "ปกติ", "109.99 ต้องได้สถานะ 'ปกติ'")

        # กรณี 2: ค่าปกติทั่วไป - ต้องเป็นปกติ
        level, status = evaluate_flood_risk(105.00)
        self.assertEqual(level, 0, "105.00 ต้องได้ level 0")
        self.assertEqual(status, "ปกติ", "105.00 ต้องได้สถานะ 'ปกติ'")

    def test_risk_other_stations(self):
        """
        ทดสอบเกณฑ์ของสถานีอื่น (TS2 และ TS5)
        เพื่อเช็คว่าระบบดึง Config ของแต่ละสถานีมาใช้ถูกไหม
        """
        # --- สถานี TS2 (ราษีไศล) เกณฑ์สูงกว่าปกติ (Warn: 119, Crit: 120) ---
        
        # 115.00 ถือว่าน้ำท่วมที่อื่น แต่ที่นี่ยัง "ปกติ"
        level, status = evaluate_flood_risk(115.00, station_id='TS2')
        self.assertEqual(level, 0, "TS2: 115.00 ต้องปกติ")

        # 119.50 ต้อง "เฝ้าระวัง"
        level, status = evaluate_flood_risk(119.50, station_id='TS2')
        self.assertEqual(level, 1, "TS2: 119.50 ต้องเฝ้าระวัง")

        # --- สถานี TS5 (แก่งสะพือ) (Warn: 111, Crit: 112) ---
        # ลองเทสค่าวิกฤต
        level, status = evaluate_flood_risk(112.50, station_id='TS5')
        self.assertEqual(level, 2, "TS5: 112.50 ต้องวิกฤต")

    def test_risk_unknown_station_fallback(self):
        """
        ทดสอบกรณีใส่ ID สถานีมั่วๆ หรือไม่มีในระบบ
        ระบบต้องกลับไปใช้เกณฑ์ Default (TS16) -> Warn: 110
        """
        # ใส่ ID มั่วๆ 'XXX99' แต่ระดับน้ำ 111.00 (ซึ่งเกินเกณฑ์ TS16)
        level, status = evaluate_flood_risk(111.00, station_id='XXX99')
        
        # ต้องใช้เกณฑ์ TS16 ตัดสิน คือเป็น "เฝ้าระวัง"
        self.assertEqual(level, 1, "Unknown Station ต้องใช้เกณฑ์ Default (TS16)")
