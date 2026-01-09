import pandas as pd
import numpy as np
import sys
import os

# ตั้งค่าเพื่อให้ Python หาไฟล์ในโฟลเดอร์ pages เจอ
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'UFAsite.settings')
django.setup()

from pages.models import WaterLevels

# ✅ Import ฟังก์ชันประเมินความเสี่ยงเข้ามาใช้
try:
    from pages.risk_calculator import evaluate_flood_risk
except ImportError:
    # เผื่อกรณีรันแล้วหาไฟล์ไม่เจอ จะใช้ Logic สำรองนี้แทน
    def evaluate_flood_risk(val, station_id='TS16'):
        if val >= 112.00: return (2, "🔴 วิกฤต (Critical)")
        elif val >= 110.00: return (1, "🟡 เฝ้าระวัง (Warning)")
        else: return (0, "🟢 ปกติ (Normal)")

# ==========================================
# 1. ดึงข้อมูลจริง (Real Data Fetching)
# ==========================================
print("🔄 กำลังดึงข้อมูลจาก Database...")

# ดึงข้อมูล: เวลา, รหัสสถานี, ระดับน้ำ
qs = WaterLevels.objects.all().values('recorded_at', 'station__station_id', 'water_level')
df_raw = pd.DataFrame(qs)

if df_raw.empty:
    print("❌ ไม่พบข้อมูลในฐานข้อมูล กรุณารันคำสั่ง scrape_data ก่อน")
    sys.exit()

# ❗ แปลงคอลัมน์ water_level เป็นตัวเลข (สำคัญ!)
# errors='coerce' จะเปลี่ยนค่าที่แปลงไม่ได้ (เช่น text) ให้เป็น NaN
df_raw['water_level'] = pd.to_numeric(df_raw['water_level'], errors='coerce')

# จัดรูปแบบข้อมูล (Pivot) ให้แต่ละสถานีเป็นคอลัมน์
# Index=เวลา, Columns=สถานี, Values=ระดับน้ำ
df = df_raw.pivot_table(index='recorded_at', columns='station__station_id', values='water_level')

# จัดการข้อมูลหาย (Resample & Interpolate)
# ปรับให้เป็นรายชั่วโมง (h) และเติมค่าที่หายไป (Linear Interpolation)
df = df.resample('h').mean().interpolate(method='linear')

# ลบแถวที่ยังมีค่าว่าง (เผื่อหัวท้ายเติมไม่ได้)
df.dropna(inplace=True)

print(f"✅ เตรียมข้อมูลเสร็จสิ้น: {len(df)} แถว")
print(df.head()) # ดูตัวอย่างข้อมูล

# ==========================================
# 2. เตรียมข้อมูลและสร้าง Feature (Preprocessing & Feature Engineering)
# ==========================================
print("🔬 กำลังสร้าง Features เพิ่มเติม (Lagged Features)...")
# สร้าง features จากข้อมูลย้อนหลัง (Lag Features) สำหรับสถานีที่เกี่ยวข้อง
for station in ['TS2', 'TS16', 'TS5']:
    for i in range(1, 4): # ย้อนหลัง 1, 2, 3 ชั่วโมง
        df[f'{station}_lag{i}h'] = df[station].shift(i)

PREDICT_HOURS = 6
df['Target_Next6H'] = df['TS16'].shift(-PREDICT_HOURS)

# ลบแถวที่มีค่าว่าง (NaN) ที่เกิดจากการ shift ทั้งหมดในขั้นตอนข้างต้น
df.dropna(inplace=True)

# อัปเดตรายการ features ที่จะใช้สอนโมเดล
features_to_use = [
    'TS2', 'TS16', 'TS5',
    'TS2_lag1h', 'TS2_lag2h', 'TS2_lag3h',
    'TS16_lag1h', 'TS16_lag2h', 'TS16_lag3h',
    'TS5_lag1h', 'TS5_lag2h', 'TS5_lag3h',
]
X = df[features_to_use]
y = df['Target_Next6H']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# ==========================================
# 3. สร้างและสอนโมเดล (Training)
# ==========================================
model = LinearRegression()
model.fit(X_train, y_train)

# ==========================================
# 4. ทดลองทำนาย (Prediction & Risk Check)
# ==========================================
print("\n🔮 ผลการพยากรณ์ล่วงหน้า 6 ชั่วโมง:")

# สมมติเหตุการณ์ 1: น้ำยังปกติ
scenario_1 = np.array([[
    # Current values (TS2, TS16, TS5)
    118.00, 108.50, 107.00,
    # Lags for TS2 (1h, 2h, 3h ago)
    117.95, 117.90, 117.85,
    # Lags for TS16 (1h, 2h, 3h ago)
    108.45, 108.40, 108.35,
    # Lags for TS5 (1h, 2h, 3h ago)
    106.95, 106.90, 106.85
]])
# สมมติเหตุการณ์ 2: น้ำเริ่มมาแรง (น้ำท่วม)
scenario_2 = np.array([[
    # Current values (TS2, TS16, TS5)
    121.50, 111.80, 111.50,
    # Lags for TS2 (rising trend)
    121.40, 121.30, 121.20,
    # Lags for TS16 (rising trend)
    111.70, 111.60, 111.50,
    # Lags for TS5 (rising trend)
    111.40, 111.30, 111.20
]])

# เลือกเหตุการณ์ที่จะทดสอบ (ลองเปลี่ยนเป็น scenario_1 หรือ scenario_2 ได้)
current_input = scenario_2

# สั่ง AI ทำนาย
predicted_level = model.predict(current_input)[0]

# ✅ นำค่าที่ทำนายได้ ไปเข้าฟังก์ชัน evaluate_flood_risk
risk_level, risk_text = evaluate_flood_risk(predicted_level, station_id='TS16')

print(f"-" * 40)
print(f"📥 ข้อมูลปัจจุบัน (Input):")
print(f"   TS2 (ต้นน้ำ): {current_input[0][0]:.2f} ม.")
print(f"   TS16 (เมือง): {current_input[0][1]:.2f} ม.")
print(f"   TS5 (ปลายน้ำ): {current_input[0][2]:.2f} ม.")
print(f"-" * 40)
print(f"📈 อีก {PREDICT_HOURS} ชม. ข้างหน้า คาดว่าระดับน้ำจะเป็น:")
print(f"   🌊 ระดับน้ำ: {predicted_level:.2f} เมตร")
print(f"   📢 สถานะความเสี่ยง: {risk_text}") # <--- แสดงผลตรงนี้
print(f"-" * 40)

# ==========================================
# 5. ประเมินผลและวาดกราฟ (Evaluation & Visualization)
# ==========================================
predictions = model.predict(X_test)

# --- ส่วนการประเมินผล ---
mae = mean_absolute_error(y_test, predictions)
rmse = np.sqrt(mean_squared_error(y_test, predictions)) # MSE -> RMSE
r2 = r2_score(y_test, predictions)

print("\n" + "="*40)
print("📊 ผลการประเมินโมเดล (บนข้อมูลทดสอบ):")
print(f"   - R-squared (R²): {r2:.4f}")
print(f"     (โมเดลอธิบายความผันผวนของข้อมูลได้ {r2:.2%})")
print(f"   - Mean Absolute Error (MAE): {mae:.4f} เมตร")
print(f"     (โดยเฉลี่ยแล้ว โมเดลทำนายคลาดเคลื่อนไป {mae:.4f} เมตร)")
print(f"   - Root Mean Squared Error (RMSE): {rmse:.4f} เมตร")
print(f"     (ค่าความคลาดเคลื่อนแบบถ่วงน้ำหนักความผิดพลาดใหญ่ๆ)")
print("="*40)


# แปลงผลทำนายเป็นสีเพื่อวาดลงกราฟ (Optional)
# (ส่วนนี้แค่โชว์กราฟเส้นเหมือนเดิมครับ)
plt.figure(figsize=(10, 5))
plt.plot(y_test.values, label='Actual', color='blue', alpha=0.5)
plt.plot(predictions, label='Predicted', color='red', linestyle='--')

# วาดเส้นขีดแดง Threshold วิกฤต (112.00)
plt.axhline(y=112.00, color='darkred', linestyle=':', label='Critical Threshold (112m)')
plt.axhline(y=110.00, color='orange', linestyle=':', label='Warning Threshold (110m)')

plt.title(f'Water Level Prediction (Next {PREDICT_HOURS} Hours)')
plt.xlabel('Time')
plt.ylabel('Water Level (m)')
plt.legend()
plt.show()