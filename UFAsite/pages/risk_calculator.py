class RiskCalculator:
    """
    คลาสสำหรับประเมินความเสี่ยงน้ำท่วมจากระดับน้ำ
    รองรับหลายสถานีด้วยเกณฑ์ที่แตกต่างกัน
    """

    STATION_THRESHOLDS = {
        'TS16': {'warn': 110.00, 'crit': 112.00},  # M.7 เมืองอุบล
        'TS2':  {'warn': 119.00, 'crit': 120.00},  # M.5 ราษีไศล (ต้นน้ำ สูงกว่า)
        'TS5':  {'warn': 111.00, 'crit': 112.00},  # M.11B แก่งสะพือ (ปลายน้ำ ต่ำกว่า)
    }

    @staticmethod
    def get_thresholds(station_id='TS16'):
        """
        ดึงค่าเกณฑ์เตือนภัยจากฐานข้อมูล (WaterStations) หากไม่มีให้ใช้ค่า Default
        """
        default_cfg = RiskCalculator.STATION_THRESHOLDS.get(
            station_id, RiskCalculator.STATION_THRESHOLDS.get('TS16', {'warn': 110.00, 'crit': 112.00})
        )
        try:
            from pages.models import WaterStations
            station = WaterStations.objects.filter(station_id=station_id).first()
            if station and station.warning_level is not None and station.critical_level is not None:
                return {
                    'warn': float(station.warning_level),
                    'crit': float(station.critical_level)
                }
        except Exception:
            pass
        return default_cfg

    @staticmethod
    def evaluate_flood_risk(water_level, station_id='TS16'):
        """
        ประเมินความเสี่ยงน้ำท่วมจากระดับน้ำ

        Args:
            water_level (float): ระดับน้ำปัจจุบัน (ม.รทก.)
            station_id (str): รหัสสถานี เช่น 'TS16'

        Returns:
            tuple: (risk_level_int, risk_status_text)
                   0=ปกติ, 1=เฝ้าระวัง, 2=วิกฤต
        """
        thresholds = RiskCalculator.get_thresholds(station_id)

        limit_warning = thresholds['warn']
        limit_critical = thresholds['crit']

        # เปรียบเทียบระดับน้ำ
        if water_level >= limit_critical:
            return 2, "วิกฤต (น้ำล้นตลิ่ง)"   # Critical
        elif water_level >= limit_warning:
            return 1, "เฝ้าระวัง"               # Warning
        else:
            return 0, "ปกติ"                    # Normal


# Alias สำหรับเรียกใช้ระดับโมดูลและ Unit Test
evaluate_flood_risk = RiskCalculator.evaluate_flood_risk
