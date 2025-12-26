STATION_THRESHOLDS = {
        'TS16': {'warn': 110.00, 'crit': 112.00},  # M.7 เมืองอุบล
        'TS2':  {'warn': 119.00, 'crit': 120.00},  # M.5 ราษีไศล (ต้นน้ำ สูงกว่า)
        'TS5':  {'warn': 111.00, 'crit': 112.00},  # M.11B แก่งสะพือ (ปลายน้ำ ต่ำกว่า)
    }

def evaluate_flood_risk(water_level, station_id='TS16'):
    """
    ฟังก์ชันประเมินความเสี่ยงน้ำท่วมจากระดับน้ำ
    (รองรับหลายสถานีด้วยเกณฑ์ที่แตกต่างกัน)
    
    Args:
        water_level (float): ระดับน้ำปัจจุบัน (ม.รทก.)
        station_id (str): รหัสสถานี เช่น 'TS16'

    Returns:
        tuple: (risk_level_int, risk_status_text)
               0=ปกติ, 1=เฝ้าระวัง, 2=วิกฤต
    """
    
    # กำหนดเกณฑ์แจ้งเตือนของแต่ละสถานี (Warning, Critical)
    # ดึงค่าเกณฑ์ของสถานีนั้นๆ (ถ้าไม่มีให้ใช้ค่า Default ของ TS16)
    thresholds = STATION_THRESHOLDS.get(station_id, STATION_THRESHOLDS['TS16'])
    
    limit_warning = thresholds['warn']
    limit_critical = thresholds['crit']

    # เปรียบเทียบระดับน้ำ
    if water_level >= limit_critical:
        return 2, "วิกฤต (น้ำล้นตลิ่ง)"  # Critical
    elif water_level >= limit_warning:
        return 1, "เฝ้าระวัง"  # Warning
    else:
        return 0, "ปกติ"  # Normal