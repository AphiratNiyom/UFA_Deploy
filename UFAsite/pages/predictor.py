import pandas as pd
import numpy as np
import joblib
from datetime import timedelta
from django.utils import timezone

from .models import WaterLevels
from .risk_calculator import evaluate_flood_risk
from sklearn.linear_model import LinearRegression

# --- Constants ---
MODEL_PATH = 'trained_model.joblib' 
PREDICT_HOURS = 6
STATIONS_FOR_FEATURES = ['TS2', 'TS16', 'TS5']
TARGET_STATION = 'TS16'

# Threshold ความผิดปกติ
ANOMALY_RISE_THRESHOLD = 0.5    # น้ำขึ้นเร็ว (Flash Flood)
BACKWATER_DIFF_THRESHOLD = 1.5  # ส่วนต่างหัวท้ายที่เริ่มน่าห่วง (ลดจาก 2.5)
BACKWATER_LEVEL_TRIGGER = 109.00 # ⚠️ เพิ่มใหม่: ถ้าน้ำยังไม่ถึงระดับนี้ ไม่ต้องเช็คน้ำหนุน

FEATURES_TO_USE = [
    'TS2', 'TS16', 'TS5',
    'TS2_lag1h', 'TS2_lag2h', 'TS2_lag3h',
    'TS16_lag1h', 'TS16_lag2h', 'TS16_lag3h',
    'TS5_lag1h', 'TS5_lag2h', 'TS5_lag3h',
]

def _prepare_dataframe(df_raw):
    """Takes raw dataframe from DB and processes it for training or prediction."""
    df_raw['water_level'] = pd.to_numeric(df_raw['water_level'], errors='coerce')
    df_raw.dropna(subset=['water_level'], inplace=True)

    df = df_raw.pivot_table(index='recorded_at', columns='station__station_id', values='water_level')

    for station in STATIONS_FOR_FEATURES:
        if station not in df.columns:
            df[station] = np.nan

    df = df.resample('h').mean()
    df = df.interpolate(method='linear', limit_direction='both')
    df.fillna(method='bfill', inplace=True)
    df.fillna(method='ffill', inplace=True)

    # Create lagged features
    for station in STATIONS_FOR_FEATURES:
        for i in range(1, 4):
            df[f'{station}_lag{i}h'] = df[station].shift(i)
    
    df.dropna(inplace=True)
    return df

def train_and_save_model():
    """Fetches data, trains a new model, and saves it."""
    # (ส่วนนี้เหมือนเดิมครับ)
    print("🔄 Starting model training process...")
    qs = WaterLevels.objects.all().values('recorded_at', 'station__station_id', 'water_level')
    if not qs.exists(): return None

    df_raw = pd.DataFrame(qs)
    df = _prepare_dataframe(df_raw)

    if df.empty: return None

    df['target'] = df[TARGET_STATION].shift(-PREDICT_HOURS)
    df.dropna(inplace=True)

    if df.empty: return None

    X = df[FEATURES_TO_USE]
    y = df['target']

    model = LinearRegression()
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)
    print("✅ Model training complete.")
    return MODEL_PATH

def load_and_predict():
    """
    โหลดโมเดลและทำนายระดับน้ำ พร้อมระบบ Hybrid 2 ชั้น:
    1. Anomaly Detection (Flash Flood)
    2. Backwater Effect (น้ำหนุน)
    """
    # 1. Load Model
    try:
        model = joblib.load(MODEL_PATH)
    except FileNotFoundError:
        return None, None, f"ไม่พบไฟล์โมเดล ({MODEL_PATH})"

    # 2. Fetch Data
    now = timezone.now()
    start_time = now - timedelta(hours=12)
    
    qs = WaterLevels.objects.filter(
        station__station_id__in=STATIONS_FOR_FEATURES,
        recorded_at__gte=start_time
    ).values('recorded_at', 'station__station_id', 'water_level')

    if not qs.exists():
        return None, None, "ไม่พบข้อมูลล่าสุด"

    # 3. Prepare Data
    df_raw = pd.DataFrame(qs)
    df_processed = _prepare_dataframe(df_raw)

    if df_processed.empty or not all(f in df_processed.columns for f in FEATURES_TO_USE):
         return None, None, "ข้อมูลไม่เพียงพอสำหรับทำนาย"

    input_vector = df_processed[FEATURES_TO_USE].tail(1)

    ts16_now = input_vector['TS16'].values[0]
    ts5_now = input_vector['TS5'].values[0]

# ====================================================
    # 🛡️ HYBRID SYSTEM: RULE-BASED CHECKS (UPDATED)
    # ====================================================
    
    warnings = []
    is_critical_logic = False

    # Check 1: Flash Flood (น้ำเหนือหลากเร็ว)
    ts2_now = input_vector['TS2'].values[0]
    ts2_prev = input_vector['TS2_lag1h'].values[0]
    ts2_rise = ts2_now - ts2_prev
    
    if ts2_rise > ANOMALY_RISE_THRESHOLD:
        warnings.append(f"น้ำเหนือหลากเร็ว (+{ts2_rise:.2f}ม./ชม.)")
        is_critical_logic = True

    # Check 2: Backwater Effect (น้ำหนุน/ระบายไม่ทัน) - ปรับปรุงใหม่ ✅
    diff = ts16_now - ts5_now
    
    # เงื่อนไขใหม่: ต้องน้ำเยอะระดับนึง (เกิน 109m) AND ส่วนต่างน้อย (อั้น)
    if ts16_now > BACKWATER_LEVEL_TRIGGER and diff < BACKWATER_DIFF_THRESHOLD:
        warnings.append(f"ภาวะน้ำหนุนระบายยาก (Diff {diff:.2f}ม.)")
        is_critical_logic = True
    
    # (Optional Debug: ปริ้นดูว่าปัจจุบันรอดเพราะอะไร)
    print(f"DEBUG: TS16={ts16_now}, Diff={diff}, TriggerLevel={BACKWATER_LEVEL_TRIGGER}")

    # ====================================================
    # 🤖 AI PREDICTION
    # ====================================================
    
    predicted_level = model.predict(input_vector)[0]
    risk_level, risk_text = evaluate_flood_risk(predicted_level, station_id=TARGET_STATION)

    # ====================================================
    # 🏁 FINAL DECISION
    # ====================================================
    
    if is_critical_logic:
        # ถ้าเจอกฎพิเศษ ให้ Override ข้อความแจ้งเตือน
        warning_msg = " และ ".join(warnings)
        risk_text = f"🟠 เฝ้าระวังพิเศษ! ({warning_msg})"
        
        # บังคับยกระดับความเสี่ยงเป็นอย่างน้อย Level 1
        if risk_level == 0:
            risk_level = 1
            
    return predicted_level, risk_level, risk_text