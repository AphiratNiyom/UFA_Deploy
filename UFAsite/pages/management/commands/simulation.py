import pandas as pd
import numpy as np
import sys
import os
from django.core.management.base import BaseCommand
from sklearn.model_selection import train_test_split, KFold
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import matplotlib.pyplot as plt
from pages.models import WaterLevels

# Import risk calculator
try:
    from pages.risk_calculator import evaluate_flood_risk
except ImportError:
    def evaluate_flood_risk(val, station_id='TS16'):
        if val >= 112.00: return (2, "🔴 วิกฤต (Critical)")
        elif val >= 110.00: return (1, "🟡 เฝ้าระวัง (Warning)")
        else: return (0, "🟢 ปกติ (Normal)")

class Command(BaseCommand):
    help = 'Run flood risk simulation and anomaly detection test'

    def handle(self, *args, **options):
        # ==========================================
        # 1. ดึงข้อมูลจริง (Real Data Fetching)
        # ==========================================
        print("🔄 กำลังดึงข้อมูลจาก Database...")
        qs = WaterLevels.objects.all().values('recorded_at', 'station__station_id', 'water_level')
        df_raw = pd.DataFrame(qs)

        if df_raw.empty:
            self.stdout.write(self.style.ERROR("❌ ไม่พบข้อมูลในฐานข้อมูล กรุณารันคำสั่ง scrape_data ก่อน"))
            return

        # Clean & Pivot Data
        df_raw['water_level'] = pd.to_numeric(df_raw['water_level'], errors='coerce')
        df = df_raw.pivot_table(index='recorded_at', columns='station__station_id', values='water_level')
        df = df.resample('h').mean().interpolate(method='linear')
        df.dropna(inplace=True)
        print(f"✅ เตรียมข้อมูลพื้นฐานเสร็จสิ้น: {len(df)} แถว")

        # ==========================================
        # 🚨 SIMULATION MODE: จำลองเหตุการณ์น้ำท่วม
        # ==========================================
        SIMULATE_FLOOD = True 

        if SIMULATE_FLOOD:
            print("\n" + "!"*50)
            print("🌊 SIMULATION ACTIVATED: กำลังสร้างข้อมูลน้ำท่วมจำลอง...")
            print("!"*50)
            
            rows = len(df)
            center = rows // 2
            
            def create_flood_wave(length, center, peak_height, width, lag):
                x = np.arange(length)
                return peak_height * np.exp(-((x - (center + lag))**2) / (2 * width**2))

            wave_width = 48
            flood_height = 4.5

            if 'TS2' in df.columns:
                df['TS2'] += create_flood_wave(rows, center, flood_height + 1.0, wave_width, lag=0)
            if 'TS16' in df.columns:
                df['TS16'] += create_flood_wave(rows, center, flood_height, wave_width, lag=12)
            if 'TS5' in df.columns:
                df['TS5'] += create_flood_wave(rows, center, flood_height - 0.5, wave_width, lag=20)

            print("✅ สร้างข้อมูลจำลองเสร็จสิ้น: ระดับน้ำจะมีการเปลี่ยนแปลงสูง-ต่ำแล้ว")

        # ==========================================
        # 2. สร้าง Feature Engineering (Lags)
        # ==========================================
        print("🔬 กำลังสร้าง Lagged Features (ข้อมูลย้อนหลัง)...")
        for station in ['TS2', 'TS16', 'TS5']:
            if station in df.columns:
                for i in range(1, 4): 
                    df[f'{station}_lag{i}h'] = df[station].shift(i)

        feature_cols = [c for c in df.columns if 'lag' in c or c in ['TS2', 'TS16', 'TS5']]
        df_features = df.dropna()

        # ==========================================
        # 2.5 การทดลองหาช่วงเวลาที่ดีที่สุด
        # ==========================================
        print("\n" + "="*50)
        print("🧪 EXPERIMENT: ค้นหาระยะเวลาพยากรณ์ที่เหมาะสมที่สุด")
        print("="*50)

        horizons = [1, 3, 6, 12, 24]
        best_score = -999
        best_horizon = 6

        for h in horizons:
            df_temp = df_features.copy()
            df_temp['Target'] = df_temp['TS16'].shift(-h)
            df_temp.dropna(inplace=True)
            
            if len(df_temp) < 50:
                continue

            X_exp = df_temp[feature_cols]
            y_exp = df_temp['Target']
            
            X_tr, X_te, y_tr, y_te = train_test_split(X_exp, y_exp, test_size=0.2, shuffle=False)
            
            model_exp = LinearRegression()
            model_exp.fit(X_tr, y_tr)
            
            score = model_exp.score(X_te, y_te)
            mae = mean_absolute_error(y_te, model_exp.predict(X_te))
            
            print(f"   ⏳ พยากรณ์ล่วงหน้า {h:02d} ชม. -> R² = {score:.4f} | MAE = {mae:.4f} ม.")

            if score > best_score:
                best_score = score
                best_horizon = h

        best_horizon = 6 
        print(f"\n✅ เลือกใช้ระยะเวลาพยากรณ์: {best_horizon} ชั่วโมง")
        print("="*50)

        # ==========================================
        # 3. เตรียมข้อมูลจริงสำหรับ Final Model
        # ==========================================
        PREDICT_HOURS = best_horizon
        df_final = df_features.copy()
        df_final['Target_Next'] = df_final['TS16'].shift(-PREDICT_HOURS)
        df_final.dropna(inplace=True)

        X = df_final[feature_cols]
        y = df_final['Target_Next']

        # ==========================================
        # 4. ประเมินความแม่นยำด้วย K-Fold
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

        # Train Final Model
        final_model = LinearRegression()
        final_model.fit(X, y)
        print("✅ Final Model Trained and Ready.")

        # ==========================================
        # 5. Hybrid System Test
        # ==========================================
        print("\n" + "="*50)
        print("🛡️ Hybrid System Test (ML + Anomaly Rules)")
        print("="*50)

        if not X.empty:
            last_row = X.iloc[[-1]].copy().values
            
            if 'TS2' in feature_cols and 'TS2_lag1h' in feature_cols:
                ts2_idx = feature_cols.index('TS2')
                ts2_lag1_idx = feature_cols.index('TS2_lag1h')

                scenario_input = last_row.copy()
                scenario_input[0, ts2_idx] += 1.5 
                
                ANOMALY_THRESHOLD = 0.5

                def predict_with_hybrid(input_data):
                    val_now = input_data[0, ts2_idx]
                    val_prev = input_data[0, ts2_lag1_idx]
                    diff = val_now - val_prev
                    
                    pred_val = final_model.predict(input_data)[0]
                    risk_lvl, risk_txt = evaluate_flood_risk(pred_val, 'TS16')
                    
                    print(f"--- Input Analysis ---")
                    print(f"   TS2 Change: {diff:+.2f} m (Threshold: {ANOMALY_THRESHOLD} m)")
                    print(f"   ML Prediction ({PREDICT_HOURS}h ahead): {pred_val:.2f} m")
                    
                    if diff > ANOMALY_THRESHOLD:
                        print("🚨 ANOMALY DETECTED: น้ำขึ้นเร็วผิดปกติ!")
                        return pred_val, "🟠 เฝ้าระวังพิเศษ (Flash Flood Risk)"
                    else:
                        print("✅ Pattern ปกติ")
                        return pred_val, risk_txt

                pred, status = predict_with_hybrid(scenario_input)
                print(f"📢 Final Status: {status}")

        # ==========================================
        # 6. Plotting
        # ==========================================
        print("\n📈 Plotting Full Graph...")
        all_predictions = final_model.predict(X)

        plt.figure(figsize=(12, 6))
        plt.plot(y.index, y, label='Actual Level', color='blue', alpha=0.6, linewidth=2)
        plt.plot(y.index, all_predictions, label=f'Predicted (Horizon {PREDICT_HOURS}h)', color='red', linestyle='--', linewidth=1.5)
        plt.axhline(y=112.00, color='darkred', linestyle=':', label='Critical (112m)')
        plt.axhline(y=110.00, color='orange', linestyle=':', label='Warning (110m)')

        if SIMULATE_FLOOD and len(y) > 100:
             plt.axvspan(y.index[-100], y.index[-1], color='yellow', alpha=0.1, label='Simulation Area')

        plt.title(f'Water Level Prediction: Full Timeline Simulation')
        plt.ylabel('Water Level (m)')
        plt.legend(loc='upper left')
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.tight_layout()
        plt.show()
