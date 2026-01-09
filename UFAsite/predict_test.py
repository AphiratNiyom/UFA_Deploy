import pandas as pd
import numpy as np
import sys
import os


# ตั้งค่าเพื่อให้ Python หาไฟล์ในโฟลเดอร์ pages เจอ
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sklearn.model_selection import train_test_split, KFold
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import django

# Setup Django Context
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'UFAsite.settings')
django.setup()

from pages.models import WaterLevels

# ✅ Import ฟังก์ชันประเมินความเสี่ยง
try:
    from pages.risk_calculator import evaluate_flood_risk
except ImportError:
    def evaluate_flood_risk(val, station_id='TS16'):
        if val >= 112.00: return (2, "🔴 วิกฤต (Critical)")
        elif val >= 110.00: return (1, "🟡 เฝ้าระวัง (Warning)")
        else: return (0, "🟢 ปกติ (Normal)")

# ==========================================
# 1. ดึงข้อมูลจริง (Real Data Fetching)
# ==========================================
print("🔄 กำลังดึงข้อมูลจาก Database...")
qs = WaterLevels.objects.all().values('recorded_at', 'station__station_id', 'water_level')
df_raw = pd.DataFrame(qs)

if df_raw.empty:
    print("❌ ไม่พบข้อมูลในฐานข้อมูล กรุณารันคำสั่ง scrape_data ก่อน")
    sys.exit()

# Clean & Pivot Data
df_raw['water_level'] = pd.to_numeric(df_raw['water_level'], errors='coerce')
df = df_raw.pivot_table(index='recorded_at', columns='station__station_id', values='water_level')
df = df.resample('h').mean().interpolate(method='linear')
df.dropna(inplace=True)
print(f"✅ เตรียมข้อมูลพื้นฐานเสร็จสิ้น: {len(df)} แถว")

# ==========================================
# 🚨 SIMULATION MODE: จำลองเหตุการณ์น้ำท่วม (สำหรับทดสอบตอนน้ำนิ่ง)
# ==========================================
SIMULATE_FLOOD = False  # <--- ตั้งเป็น False เมื่อต้องการใช้ข้อมูลจริงล้วนๆ

if SIMULATE_FLOOD:
    print("\n" + "!"*50)
    print("🌊 SIMULATION ACTIVATED: กำลังสร้างข้อมูลน้ำท่วมจำลอง...")
    print("!"*50)
    
    # สร้าง Curve น้ำหลากแบบระฆังคว่ำ (Gaussian Bell Curve)
    # ให้ TS2 (ต้นน้ำ) มาก่อน, TS16 (เมือง) ตามมา, TS5 (ปลายน้ำ) ตามสุดท้าย
    rows = len(df)
    center = rows // 2  # ให้ยอดน้ำท่วมอยู่ตรงกลางช่วงเวลาที่มีข้อมูล
    
    # ฟังก์ชันสร้างคลื่นน้ำ
    def create_flood_wave(length, center, peak_height, width, lag):
        x = np.arange(length)
        return peak_height * np.exp(-((x - (center + lag))**2) / (2 * width**2))

    # ความกว้างของลูกคลื่น (Width) และความสูงที่เพิ่มขึ้น (Height)
    wave_width = 48  # กินเวลาประมาณ 2 วัน (48 ชม.)
    flood_height = 4.5 # น้ำสูงขึ้น 4.5 เมตร

    # ฉีดข้อมูลเข้าไปใน DataFrame เดิม
    # TS2: มาก่อน (Lag = 0)
    df['TS2'] += create_flood_wave(rows, center, flood_height + 1.0, wave_width, lag=0)
    
    # TS16: มาช้ากว่าต้นน้ำ 12 ชม. (Lag = 12)
    df['TS16'] += create_flood_wave(rows, center, flood_height, wave_width, lag=12)
    
    # TS5: มาช้าสุด (Lag = 20)
    df['TS5'] += create_flood_wave(rows, center, flood_height - 0.5, wave_width, lag=20)

    print("✅ สร้างข้อมูลจำลองเสร็จสิ้น: ระดับน้ำจะมีการเปลี่ยนแปลงสูง-ต่ำแล้ว")

# ==========================================
# 2. สร้าง Feature Engineering (Lags)
# ==========================================
print("🔬 กำลังสร้าง Lagged Features (ข้อมูลย้อนหลัง)...")
# สร้างตัวแปรย้อนหลัง 1-3 ชม. ของทุกสถานีเพื่อใช้เป็น Input
for station in ['TS2', 'TS16', 'TS5']:
    if station in df.columns:
        for i in range(1, 4): 
            df[f'{station}_lag{i}h'] = df[station].shift(i)

# เลือก Features ที่จะใช้เป็น Input (X)
feature_cols = [c for c in df.columns if 'lag' in c or c in ['TS2', 'TS16', 'TS5']]
df_features = df.dropna() # Drop แถวแรกๆ ที่ไม่มี Lag

# ==========================================
# 🆕 2.5 การทดลองหาช่วงเวลาที่ดีที่สุด (Experiment Loop)
# ==========================================
print("\n" + "="*50)
print("🧪 EXPERIMENT: ค้นหาระยะเวลาพยากรณ์ที่เหมาะสมที่สุด")
print("="*50)

horizons = [1, 3, 6, 12, 24] # ชั่วโมงที่ต้องการทดสอบ
results = []
best_score = -999
best_horizon = 6 # ค่า Default

for h in horizons:
    # สร้าง Target เฉพาะสำหรับ Loop นี้
    df_temp = df_features.copy()
    df_temp['Target'] = df_temp['TS16'].shift(-h) # Shift ข้อมูลเพื่อทำนายอนาคต h ชม.
    df_temp.dropna(inplace=True)
    
    if len(df_temp) < 50: # ถ้าข้อมูลน้อยเกินไปข้าม
        continue

    X_exp = df_temp[feature_cols]
    y_exp = df_temp['Target']
    
    # Split ง่ายๆ เพื่อทดสอบ (80/20)
    X_tr, X_te, y_tr, y_te = train_test_split(X_exp, y_exp, test_size=0.2, shuffle=False)
    
    model_exp = LinearRegression()
    model_exp.fit(X_tr, y_tr)
    
    score = model_exp.score(X_te, y_te) # R2 Score
    mae = mean_absolute_error(y_te, model_exp.predict(X_te))
    
    results.append({'Horizon': h, 'R2': score, 'MAE': mae})
    print(f"   ⏳ พยากรณ์ล่วงหน้า {h:02d} ชม. -> R² = {score:.4f} | MAE = {mae:.4f} ม.")

    # Logic การเลือก: เลือกอันที่แม่นยำที่สุด แต่ต้องเป็นไปได้จริง
    # (ถ้า R2 ต่างกันไม่มาก จะเลือกเวลาที่นานกว่าเพื่อให้เตรียมตัวทัน)
    if score > best_score:
        best_score = score
        # หมายเหตุ: ในทางปฏิบัติเราอาจเลือก 6 ชม. แม้ 1 ชม. จะแม่นกว่า 
        # แต่นี่คือ Code ทดสอบ ขอเลือกตามความแม่นยำสูงสุดไปก่อน
        best_horizon = h

# กรณีบังคับใช้ 6 ชั่วโมงถ้าผลออกมาใกล้เคียงกัน (Uncomment บรรทัดล่างถ้าต้องการ Fix)
best_horizon = 6 

print(f"\n✅ เลือกใช้ระยะเวลาพยากรณ์: {best_horizon} ชั่วโมง (เพื่อใช้ในขั้นตอนต่อไป)")
print("="*50)

# ==========================================
# 3. เตรียมข้อมูลจริงสำหรับ Final Model (ตาม Best Horizon)
# ==========================================
PREDICT_HOURS = best_horizon
df_final = df_features.copy()
df_final['Target_Next'] = df_final['TS16'].shift(-PREDICT_HOURS)
df_final.dropna(inplace=True)

X = df_final[feature_cols]
y = df_final['Target_Next']

# ==========================================
# 4. ประเมินความแม่นยำด้วย K-Fold (Detailed Evaluation)
# ==========================================
print(f"\n🧐 ประเมินโมเดลจริง (Prediction Horizon: {PREDICT_HOURS}h) ด้วย K-Fold...")
kf = KFold(n_splits=5, shuffle=False)
model_final = LinearRegression()
mae_scores = []
r2_scores = []

for i, (train_idx, test_idx) in enumerate(kf.split(X)):
    X_train_fold, X_test_fold = X.iloc[train_idx], X.iloc[test_idx]
    y_train_fold, y_test_fold = y.iloc[train_idx], y.iloc[test_idx]
    
    model_final.fit(X_train_fold, y_train_fold)
    preds = model_final.predict(X_test_fold)
    
    mae_scores.append(mean_absolute_error(y_test_fold, preds))
    r2_scores.append(r2_score(y_test_fold, preds))

print(f"📊 ผลลัพธ์เฉลี่ย: R² = {np.mean(r2_scores):.4f}, MAE = {np.mean(mae_scores):.4f} เมตร")

# Train Final Model with ALL data
final_model = LinearRegression()
final_model.fit(X, y)
print("✅ Final Model Trained and Ready.")

# ==========================================
# 5. Hybrid System Test (Anomaly Detection)
# ==========================================
print("\n" + "="*50)
print("🛡️ Hybrid System Test (ML + Anomaly Rules)")
print("="*50)

# สร้างข้อมูลจำลอง: กรณีน้ำขึ้นกระทันหันผิดปกติ (Sudden Rise)
# เราต้องสร้าง shape ให้ตรงกับ feature_cols ที่มี
# สมมติว่ามี 3 สถานี + 3 lags ต่อสถานี = 12 columns
# ลองดึงแถวล่าสุดมาเป็นแม่แบบ
last_row = X.iloc[[-1]].copy().values
# จำลองว่าค่าปัจจุบันของ TS2 (ต้นน้ำ) พุ่งสูงขึ้น 1.5 เมตรทันที
# (สมมติว่า TS2 อยู่ column แรกๆ - ต้องเช็ค index ให้แม่นยำในงานจริง)
# เพื่อความง่ายในตัวอย่างนี้ เราจะ Mock array ขึ้นมาใหม่ให้ size เท่ากัน

# หา index ของ TS2 ใน feature_cols
ts2_idx = feature_cols.index('TS2')
ts2_lag1_idx = feature_cols.index('TS2_lag1h')

# สร้าง Scenario
scenario_input = last_row.copy()
scenario_input[0, ts2_idx] += 1.5 # เพิ่มระดับน้ำปัจจุบัน 1.5 เมตร (Anomaly)

ANOMALY_THRESHOLD = 0.5 # เมตร

def predict_with_hybrid(input_data):
    # 1. Check Rule-Based
    val_now = input_data[0, ts2_idx]
    val_prev = input_data[0, ts2_lag1_idx]
    diff = val_now - val_prev
    
    # 2. Predict ML
    pred_val = final_model.predict(input_data)[0]
    risk_lvl, risk_txt = evaluate_flood_risk(pred_val, 'TS16')
    
    print(f"--- Input Analysis ---")
    print(f"   TS2 Change: {diff:+.2f} m (Threshold: {ANOMALY_THRESHOLD} m)")
    print(f"   ML Prediction ({PREDICT_HOURS}h ahead): {pred_val:.2f} m")
    
    # 3. Combine
    if diff > ANOMALY_THRESHOLD:
        print("🚨 ANOMALY DETECTED: น้ำขึ้นเร็วผิดปกติ!")
        return pred_val, "🟠 เฝ้าระวังพิเศษ (Flash Flood Risk)"
    else:
        print("✅ Pattern ปกติ")
        return pred_val, risk_txt

# Run Test
pred, status = predict_with_hybrid(scenario_input)
print(f"📢 Final Status: {status}")

# ==========================================
# 6. ประเมินผลและวาดกราฟ (Visualization - Full Timeline)
# ==========================================
print("\n📈 Plotting Full Graph...")

# ใช้โมเดลทำนายข้อมูล (X คือข้อมูลที่ตัด NaN ออกแล้ว เท่ากับ y)
all_predictions = final_model.predict(X)

plt.figure(figsize=(12, 6))

# ✅ แก้ไขจุดที่ Error: เปลี่ยน df.index เป็น y.index
# วาดเส้นจริง (สีน้ำเงิน)
plt.plot(y.index, y, label='Actual Level', color='blue', alpha=0.6, linewidth=2)

# ✅ แก้ไขแกน X ของเส้นทำนายด้วยเช่นกัน
# วาดเส้นทำนาย (สีแดงประ)
plt.plot(y.index, all_predictions, label=f'Predicted (Horizon {PREDICT_HOURS}h)', color='red', linestyle='--', linewidth=1.5)

# เส้นวิกฤต
plt.axhline(y=112.00, color='darkred', linestyle=':', label='Critical (112m)')
plt.axhline(y=110.00, color='orange', linestyle=':', label='Warning (110m)')

# ไฮไลท์ช่วงที่เกิด Simulation (ช่วงท้าย)
if 'SIMULATE_FLOOD' in globals() and SIMULATE_FLOOD:
    # ใช้ y.index แทน df.index เพื่อกัน error
    plt.axvspan(y.index[-100], y.index[-1], color='yellow', alpha=0.1, label='Simulation Area')

plt.title(f'Water Level Prediction: Full Timeline Simulation')
plt.ylabel('Water Level (m)')
plt.legend(loc='upper left')
plt.grid(True, which='both', linestyle='--', linewidth=0.5)
plt.tight_layout()
plt.show()