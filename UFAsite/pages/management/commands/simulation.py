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
from pages.predictor import Predictor

# Import risk calculator
    from pages.risk_calculator import RiskCalculator
except ImportError:
    pass

class Command(BaseCommand):
    help = 'Run flood risk simulation and anomaly detection test'

    def handle(self, *args, **options):
        # ==========================================
        # 1. ดึงข้อมูลจริง (Real Data Fetching)
        # ==========================================
        self.stdout.write("\n" + "="*55)
        self.stdout.write("🚀  UFA FLOOD RISK SIMULATION")
        self.stdout.write("="*55)
        self.stdout.write("🔄 กำลังดึงข้อมูลจาก Database...")

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
        total_rows = len(df)
        self.stdout.write(self.style.SUCCESS(f"✅ เตรียมข้อมูลพื้นฐานเสร็จสิ้น: {total_rows:,} แถว"))

        # ==========================================
        # 🚨 SIMULATION MODE: จำลองเหตุการณ์น้ำท่วม
        # ==========================================
        SIMULATE_FLOOD = False

        if SIMULATE_FLOOD:
            self.stdout.write(self.style.WARNING("🌊 กำลังสร้างข้อมูลน้ำท่วมจำลอง..."))

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

            self.stdout.write(self.style.SUCCESS("✅ สร้างข้อมูลจำลองเสร็จสิ้น: ระดับน้ำมีการเปลี่ยนแปลงสูง-ต่ำแล้ว"))
        else:
            self.stdout.write("ℹ️  Simulation Mode: ปิดอยู่ (ใช้ข้อมูลจริงจาก DB)")

        # ==========================================
        # 2. สร้าง Feature Engineering (Lags)
        # ==========================================
        self.stdout.write("\n" + "-"*55)
        self.stdout.write("🔬 กำลังสร้าง Lagged Features (ข้อมูลย้อนหลัง)...")
        lag_count = 0
        for station in ['TS2', 'TS16', 'TS5']:
            if station in df.columns:
                for i in range(1, 4):
                    df[f'{station}_lag{i}h'] = df[station].shift(i)
                    lag_count += 1

        feature_cols = [c for c in df.columns if 'lag' in c or c in ['TS2', 'TS16', 'TS5']]
        df_features = df.dropna()
        self.stdout.write(self.style.SUCCESS(
            f"✅ Feature Engineering เสร็จสิ้น: {len(feature_cols)} features ({lag_count} lag columns)"
        ))

        # ==========================================
        # 2.5 การทดลองหาช่วงเวลาที่ดีที่สุด
        # ==========================================
        self.stdout.write("\n" + "="*55)
        self.stdout.write("🧪 EXPERIMENT: ค้นหาระยะเวลาพยากรณ์ที่เหมาะสมที่สุด")
        self.stdout.write("="*55)

        horizons = [1, 3, 6, 12, 24]
        best_score = -999
        best_horizon = 6
        experiment_results = {}

        for h in horizons:
            df_temp = df_features.copy()
            df_temp['Target'] = df_temp['TS16'].shift(-h)
            df_temp.dropna(inplace=True)

            if len(df_temp) < 50:
                self.stdout.write(self.style.WARNING(f"   ⚠️  Horizon {h:02d}h: ข้อมูลน้อยเกินไป (< 50 แถว) — ข้าม"))
                continue

            X_exp = df_temp[feature_cols]
            y_exp = df_temp['Target']

            X_tr, X_te, y_tr, y_te = train_test_split(X_exp, y_exp, test_size=0.2, shuffle=False)

            model_exp = LinearRegression()
            model_exp.fit(X_tr, y_tr)

            score = model_exp.score(X_te, y_te)
            mae = mean_absolute_error(y_te, model_exp.predict(X_te))
            experiment_results[h] = {'r2': score, 'mae': mae}

            marker = " ⬅ best" if score > best_score else ""
            self.stdout.write(
                f"   ⏳ พยากรณ์ล่วงหน้า {h:02d} ชม. -> R² = {score:.4f} | MAE = {mae:.4f} ม.{marker}"
            )

            if score > best_score:
                best_score = score
                best_horizon = h

        # Override ด้วยค่า fixed ที่ calibrate แล้ว
        auto_best = best_horizon
        best_horizon = 6
        self.stdout.write("")
        if auto_best != best_horizon:
            self.stdout.write(self.style.WARNING(
                f"⚠️  Auto-selected horizon = {auto_best}h "
                f"แต่ override เป็น {best_horizon}h (ค่า calibrated คงที่เพื่อความเสถียร)"
            ))
        else:
            self.stdout.write(
                f"ℹ️  Auto-selected horizon = {auto_best}h ตรงกับค่า calibrated ({best_horizon}h)"
            )
        self.stdout.write(self.style.SUCCESS(f"✅ เลือกใช้ระยะเวลาพยากรณ์: {best_horizon} ชั่วโมง"))
        self.stdout.write("="*55)

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
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write(f"🧐 K-Fold Cross Validation (Horizon: {PREDICT_HOURS}h, k=5)")
        self.stdout.write("="*55)

        kf = KFold(n_splits=5, shuffle=False)
        model_final = LinearRegression()
        mae_scores = []
        r2_scores = []

        for i, (train_idx, test_idx) in enumerate(kf.split(X)):
            X_train_fold, X_test_fold = X.iloc[train_idx], X.iloc[test_idx]
            y_train_fold, y_test_fold = y.iloc[train_idx], y.iloc[test_idx]

            model_final.fit(X_train_fold, y_train_fold)
            preds = model_final.predict(X_test_fold)

            fold_mae = mean_absolute_error(y_test_fold, preds)
            fold_r2  = r2_score(y_test_fold, preds)
            mae_scores.append(fold_mae)
            r2_scores.append(fold_r2)

            self.stdout.write(
                f"   Fold {i+1}/5 | Train: {len(train_idx):,} | Test: {len(test_idx):,} "
                f"| R² = {fold_r2:.4f} | MAE = {fold_mae:.4f} ม."
            )

        avg_r2  = np.mean(r2_scores)
        avg_mae = np.mean(mae_scores)
        self.stdout.write("-"*55)
        self.stdout.write(
            self.style.SUCCESS(f"📊 เฉลี่ย K-Fold: R² = {avg_r2:.4f} | MAE = {avg_mae:.4f} เมตร")
        )

        # Train Final Model บน dataset ทั้งหมด
        final_model = LinearRegression()
        final_model.fit(X, y)
        self.stdout.write(self.style.SUCCESS("✅ Final Model Trained on Full Dataset — Ready"))

        # ==========================================
        # 5. Hybrid System Test
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("🛡️  Hybrid System Test (ML + Anomaly Rules)")
        self.stdout.write("="*55)

        final_status = "N/A"
        pred_val_out = None

        if not X.empty:
            last_row = X.iloc[[-1]].copy().values

            if 'TS2' in feature_cols and 'TS2_lag1h' in feature_cols:
                ts2_idx      = feature_cols.index('TS2')
                ts2_lag1_idx = feature_cols.index('TS2_lag1h')

                scenario_input = last_row.copy()
                scenario_input[0, ts2_idx] += 1.5

                ANOMALY_THRESHOLD = 0.5

                def predict_with_hybrid(input_data):
                    val_now  = input_data[0, ts2_idx]
                    val_prev = input_data[0, ts2_lag1_idx]
                    diff     = val_now - val_prev

                    pred     = final_model.predict(input_data)[0]
                    risk_lvl, risk_txt = RiskCalculator.evaluate_flood_risk(pred, 'TS16')

                    self.stdout.write("--- Input Analysis ---")
                    self.stdout.write(f"   TS2 เปลี่ยนแปลง   : {diff:+.2f} ม. (Threshold: ±{ANOMALY_THRESHOLD} ม.)")
                    self.stdout.write(f"   ML Prediction ({PREDICT_HOURS}h): {pred:.4f} ม.")

                    if diff > ANOMALY_THRESHOLD:
                        self.stdout.write(self.style.ERROR(
                            "🚨 ANOMALY DETECTED: น้ำขึ้นเร็วผิดปกติ!"
                        ))
                        return pred, "🟠 เฝ้าระวังพิเศษ (Flash Flood Risk)"
                    else:
                        self.stdout.write(self.style.SUCCESS("✅ Pattern ปกติ ไม่พบความผิดปกติ"))
                        return pred, risk_txt

                pred_val_out, final_status = predict_with_hybrid(scenario_input)
                self.stdout.write(self.style.SUCCESS(f"📢 Final Status: {final_status}"))
            else:
                self.stdout.write(self.style.WARNING("⚠️  ไม่พบ TS2 / TS2_lag1h ใน features — ข้าม Hybrid Test"))
        else:
            self.stdout.write(self.style.WARNING("⚠️  Dataset ว่างเปล่า — ข้าม Hybrid Test"))

        # ==========================================
        # 6. Plotting
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("📈 กำลัง Plot กราฟ Full Timeline...")
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
        self.stdout.write(self.style.SUCCESS("✅ กราฟพร้อมแสดงผล"))
        plt.show()

        # ==========================================
        # 7. SUMMARY
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("📋  SIMULATION SUMMARY")
        self.stdout.write("="*55)
        self.stdout.write(f"   Mode          : {'🌊 Simulate Flood ON' if SIMULATE_FLOOD else '📡 Real Data (Simulation OFF)'}")
        self.stdout.write(f"   Data Points   : {total_rows:,} rows")
        self.stdout.write(f"   Features      : {len(feature_cols)} columns")
        self.stdout.write(f"   Horizon       : {PREDICT_HOURS}h ahead")
        self.stdout.write(f"   Avg R²        : {avg_r2:.4f}")
        self.stdout.write(f"   Avg MAE       : {avg_mae:.4f} ม.")
        if pred_val_out is not None:
            self.stdout.write(f"   ML Prediction : {pred_val_out:.4f} ม.")
        self.stdout.write(f"   Final Status  : {final_status}")
        self.stdout.write("="*55)
        self.stdout.write(self.style.SUCCESS("🎉 Simulation เสร็จสิ้นเรียบร้อย\n"))
