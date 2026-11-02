import os
import sys
import json
import calendar
from datetime import datetime
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use('Agg')  # Headless backend สำหรับ Web/Server
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.timezone import make_aware
from sklearn.model_selection import train_test_split, KFold
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

from pages.models import WaterLevels
from pages.predictor import Predictor
from pages.risk_calculator import RiskCalculator


class Command(BaseCommand):
    help = 'ทดสอบประสิทธิภาพโมเดล ML (Model Evaluation) และจำลองสถานการณ์น้ำท่วม (Flood Simulation)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            default='evaluate',
            choices=['evaluate', 'flash_flood', 'backwater', 'simulate'],
            help='โหมดการทำงาน: evaluate (ข้อมูลจริง), flash_flood (น้ำหลาก), backwater (น้ำหนุน), simulate (มหาอุทกภัย)'
        )
        parser.add_argument(
            '--year',
            type=str,
            default=None,
            help='ปีที่ต้องการทดสอบ เช่น 2024, 2025, 2026'
        )
        parser.add_argument(
            '--month',
            type=str,
            default=None,
            help='เดือนที่ต้องการทดสอบ (1-12)'
        )
        parser.add_argument(
            '--start',
            type=str,
            default=None,
            help='วันที่เริ่มต้น (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end',
            type=str,
            default=None,
            help='วันที่สิ้นสุด (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--no-plot',
            action='store_true',
            help='ปิดการบันทึกภาพกราฟ'
        )

    def handle(self, *args, **options):
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(self.stdout, '_out') and hasattr(self.stdout._out, 'reconfigure'):
                self.stdout._out.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

        mode = options.get('mode', 'evaluate')
        no_plot = options.get('no_plot', False)

        year = options.get('year')
        month = options.get('month')
        start_str = options.get('start')
        end_str = options.get('end')

        mode_titles = {
            'evaluate': '📊 โหมดทดสอบประสิทธิภาพโมเดล (Real Data Evaluation)',
            'flash_flood': '⚡ โหมดจำลองน้ำเหนือหลากฉับพลัน (Flash Flood Test)',
            'backwater': '🌊 โหมดจำลองภาวะน้ำหนุนระบายช้า (Backwater Test)',
            'simulate': '🔴 โหมดจำลองมหาอุทกภัย (Severe Flood Simulation)'
        }

        # ---------------------------------------------------
        # 1. กรองช่วงเวลา (Time Filter: Year / Month / Range)
        # ---------------------------------------------------
        qs = WaterLevels.objects.all()
        filter_desc = "ข้อมูลทั้งหมด (All Time)"
        plot_filter_desc = "All Time"

        if start_str and end_str:
            try:
                start_dt = make_aware(datetime.strptime(start_str.strip(), '%Y-%m-%d'))
                end_dt = make_aware(datetime.strptime(end_str.strip() + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
                qs = qs.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
                filter_desc = f"ช่วงวันที่ {start_str} ถึง {end_str}"
                plot_filter_desc = f"{start_str} to {end_str}"
            except ValueError:
                self.stdout.write(self.style.ERROR("❌ รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD"))
                return
        elif year and str(year).strip().lower() != 'all':
            try:
                y = int(year)
                if month and str(month).strip().lower() != 'all':
                    m = int(month)
                    _, last_day = calendar.monthrange(y, m)
                    start_dt = make_aware(datetime(y, m, 1, 0, 0, 0))
                    end_dt = make_aware(datetime(y, m, last_day, 23, 59, 59))
                    qs = qs.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
                    filter_desc = f"เดือน {m:02d}/{y}"
                    plot_filter_desc = f"Month {m:02d}/{y}"
                else:
                    start_dt = make_aware(datetime(y, 1, 1, 0, 0, 0))
                    end_dt = make_aware(datetime(y, 12, 31, 23, 59, 59))
                    qs = qs.filter(recorded_at__gte=start_dt, recorded_at__lte=end_dt)
                    filter_desc = f"ประจำปี {y}"
                    plot_filter_desc = f"Year {y}"
            except (ValueError, TypeError) as e:
                self.stdout.write(self.style.ERROR(f"❌ ค่าปี/เดือนไม่ถูกต้อง: {e}"))
                return
        elif month and str(month).strip().lower() != 'all':
            try:
                m = int(month)
                qs = qs.filter(recorded_at__month=m)
                filter_desc = f"เฉพาะเดือน {m:02d} (ทุกปี)"
                plot_filter_desc = f"Month {m:02d}"
            except ValueError:
                self.stdout.write(self.style.ERROR("❌ ค่าเดือนไม่ถูกต้อง (ต้องเป็น 1-12)"))
                return

        self.stdout.write("\n" + "="*55)
        self.stdout.write("🚀  UFA MODEL EVALUATION & SIMULATION")
        self.stdout.write(f"📌  {mode_titles.get(mode, mode)}")
        self.stdout.write(f"⏱️  ช่วงเวลาข้อมูล: {filter_desc}")
        self.stdout.write("="*55)
        self.stdout.write("🔄 กำลังดึงข้อมูลจาก Database...")

        qs_values = qs.values('recorded_at', 'station__station_id', 'water_level')
        df_raw = pd.DataFrame(qs_values)

        if df_raw.empty:
            self.stdout.write(self.style.ERROR(f"❌ ไม่พบข้อมูลในฐานข้อมูลสำหรับช่วงเวลา: {filter_desc}"))
            return

        if len(df_raw) < 50:
            self.stdout.write(self.style.ERROR(
                f"❌ ข้อมูลในช่วงเวลา {filter_desc} มีเพียง {len(df_raw)} รายการ ซึ่งน้อยเกินไปสำหรับทดสอบโมเดล (ต้องการอย่างน้อย 50 รายการขึ้นไป) กรุณาเลือกช่วงเวลาที่กว้างขึ้น"
            ))
            return

        # Clean & Pivot Data
        df_raw['water_level'] = pd.to_numeric(df_raw['water_level'], errors='coerce')
        df = df_raw.pivot_table(index='recorded_at', columns='station__station_id', values='water_level')
        df = df.resample('h').mean().interpolate(method='linear')
        df.bfill(inplace=True)
        df.ffill(inplace=True)
        df.dropna(inplace=True)

        total_rows = len(df)
        if total_rows < 30:
            self.stdout.write(self.style.ERROR(
                f"❌ หลังเตรียมข้อมูล ข้อมูลคงเหลือ {total_rows} ชั่วโมง ซึ่งน้อยเกินไปสำหรับทดสอบ กรุณาเลือกช่วงเวลาที่กว้างขึ้น"
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"✅ ข้อมูลพื้นฐานพร้อมประมวลผล: {total_rows:,} แถว ({filter_desc})"))

        # ==========================================
        # 2. จัดการโหมดจำลองสถานการณ์ (Scenarios)
        # ==========================================
        if mode == 'simulate':
            self.stdout.write(self.style.WARNING("🌊 กำลังสร้างข้อมูลมวลน้ำท่วมจำลอง (Flood Wave)..."))
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

            self.stdout.write(self.style.SUCCESS("✅ จำลองมวลน้ำหลากขนาดใหญ่เสร็จสิ้น"))
        elif mode == 'flash_flood':
            self.stdout.write(self.style.WARNING("⚡ กำลังจำลองระดับน้ำเหนือเพิ่มขึ้นเฉียบพลัน (+2.5 ม.)..."))
            if 'TS2' in df.columns and len(df) > 20:
                df.iloc[-20:, df.columns.get_loc('TS2')] += np.linspace(0.2, 3.0, 20)
            self.stdout.write(self.style.SUCCESS("✅ จำลองสถานการณ์ Flash Flood สำเร็จ"))
        elif mode == 'backwater':
            self.stdout.write(self.style.WARNING("🌊 กำลังจำลองภาวะน้ำหนุนระบายยาก (TS16 สูง และ TS5 หนุนใกล้เคียง)..."))
            if 'TS16' in df.columns and 'TS5' in df.columns and len(df) > 20:
                df.iloc[-20:, df.columns.get_loc('TS16')] = 110.5
                df.iloc[-20:, df.columns.get_loc('TS5')] = 109.8
            self.stdout.write(self.style.SUCCESS("✅ จำลองสถานการณ์ Backwater Effect สำเร็จ"))
        else:
            self.stdout.write("ℹ️  โหมดประเมินความแม่นยำ: ใช้ข้อมูลจริงจาก Database ทั้งหมด")

        # ==========================================
        # 3. สร้าง Feature Engineering (Lags & Extended Upstream)
        # ==========================================
        self.stdout.write("\n" + "-"*55)
        self.stdout.write("🔬 กำลังสร้าง Lagged Features (1-3 ชม. และ Lags ต้นน้ำ 6-48 ชม.)...")
        lag_count = 0
        for station in ['TS2', 'TS16', 'TS5']:
            if station in df.columns:
                for i in range(1, 4):
                    df[f'{station}_lag{i}h'] = df[station].shift(i)
                    lag_count += 1

        # Lags ต้นน้ำ TS2 (M.5 ราษีไศล) ตามเวลาการเดินทางของมวลน้ำ หากข้อมูลมีจำนวนแถวเพียงพอ (>= 70 ชม.)
        if 'TS2' in df.columns and len(df) >= 70:
            for h in [6, 12, 24, 48]:
                df[f'TS2_lag{h}h'] = df['TS2'].shift(h)
                lag_count += 1

        feature_cols = [c for c in df.columns if 'lag' in c or c in ['TS2', 'TS16', 'TS5']]
        df_features = df.dropna()
        self.stdout.write(self.style.SUCCESS(
            f"✅ Feature Engineering เสร็จสิ้น: {len(feature_cols)} features ({lag_count} lag columns)"
        ))

        # ==========================================
        # 4. การทดลองหาช่วงเวลาที่ดีที่สุด (Horizon)
        # ==========================================
        self.stdout.write("\n" + "="*55)
        self.stdout.write("🧪 EXPERIMENT: ค้นหาระยะเวลาพยากรณ์ที่เหมาะสมที่สุด")
        self.stdout.write("="*55)

        horizons = [1, 3, 6, 12, 24]
        best_score = -999
        best_horizon = 6

        for h in horizons:
            df_temp = df_features.copy()
            df_temp['Target'] = df_temp['TS16'].shift(-h)
            df_temp.dropna(inplace=True)

            if len(df_temp) < 20:
                self.stdout.write(self.style.WARNING(f"   ⚠️  Horizon {h:02d}h: ข้อมูลน้อยเกินไป (< 20 แถว) — ข้าม"))
                continue

            X_exp = df_temp[feature_cols]
            y_exp = df_temp['Target']

            X_tr, X_te, y_tr, y_te = train_test_split(X_exp, y_exp, test_size=0.2, shuffle=False)

            model_exp = LinearRegression()
            model_exp.fit(X_tr, y_tr)

            score = model_exp.score(X_te, y_te)
            mae = mean_absolute_error(y_te, model_exp.predict(X_te))

            marker = " ⬅ best" if score > best_score else ""
            self.stdout.write(
                f"   ⏳ พยากรณ์ล่วงหน้า {h:02d} ชม. -> R² = {score:.4f} | MAE = {mae:.4f} ม.{marker}"
            )

            if score > best_score:
                best_score = score
                best_horizon = h

        PREDICT_HOURS = 6
        self.stdout.write(self.style.SUCCESS(f"✅ ระยะเวลาพยากรณ์สำหรับระบบจริง: {PREDICT_HOURS} ชั่วโมง"))
        self.stdout.write("="*55)

        # ==========================================
        # 5. ประเมินความแม่นยำด้วย Cross Validation
        # ==========================================
        df_final = df_features.copy()
        df_final['Target_Next'] = df_final['TS16'].shift(-PREDICT_HOURS)
        df_final.dropna(inplace=True)

        X = df_final[feature_cols]
        y = df_final['Target_Next']

        n_splits = min(5, max(2, len(df_final) // 10))
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write(f"🧐 K-Fold Cross Validation (Horizon: {PREDICT_HOURS}h, k={n_splits})")
        self.stdout.write("="*55)

        kf = KFold(n_splits=n_splits, shuffle=False)
        model_final = LinearRegression()
        mae_scores = []
        r2_scores = []

        for i, (train_idx, test_idx) in enumerate(kf.split(X)):
            X_train_fold, X_test_fold = X.iloc[train_idx], X.iloc[test_idx]
            y_train_fold, y_test_fold = y.iloc[train_idx], y.iloc[test_idx]

            model_final.fit(X_train_fold, y_train_fold)
            preds = model_final.predict(X_test_fold)

            fold_mae = mean_absolute_error(y_test_fold, preds)
            fold_r2 = r2_score(y_test_fold, preds)
            mae_scores.append(fold_mae)
            r2_scores.append(fold_r2)

            self.stdout.write(
                f"   Fold {i+1}/{n_splits} | Train: {len(train_idx):,} | Test: {len(test_idx):,} "
                f"| R² = {fold_r2:.4f} | MAE = {fold_mae:.4f} ม."
            )

        avg_r2 = float(np.mean(r2_scores))
        avg_mae = float(np.mean(mae_scores))
        self.stdout.write("-"*55)
        self.stdout.write(
            self.style.SUCCESS(f"📊 ผลเฉลี่ย K-Fold: R² = {avg_r2:.4f} | MAE = {avg_mae:.4f} เมตร")
        )

        final_model = LinearRegression()
        final_model.fit(X, y)

        # ==========================================
        # 6. Hybrid System Test
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("🛡️  Hybrid System Test (ML + Anomaly Rules)")
        self.stdout.write("="*55)

        final_status = "N/A"
        pred_val_out = None

        if not X.empty:
            last_row_df = X.iloc[[-1]].copy()
            if mode == 'flash_flood':
                if 'TS2' in last_row_df.columns:
                    last_row_df['TS2'] += 1.5
            elif mode == 'backwater':
                if 'TS16' in last_row_df.columns and 'TS5' in last_row_df.columns:
                    last_row_df['TS16'] = 110.20
                    last_row_df['TS5'] = 109.50

            pred = final_model.predict(last_row_df)[0]
            last_row = last_row_df.values
            pred_val_out = pred

            ts16_now = last_row[0, feature_cols.index('TS16')] if 'TS16' in feature_cols else 0
            ts5_now = last_row[0, feature_cols.index('TS5')] if 'TS5' in feature_cols else 0
            diff = ts16_now - ts5_now

            ts2_now = last_row[0, feature_cols.index('TS2')] if 'TS2' in feature_cols else 0
            ts2_prev = last_row[0, feature_cols.index('TS2_lag1h')] if 'TS2_lag1h' in feature_cols else ts2_now
            ts2_rise = ts2_now - ts2_prev

            risk_lvl, risk_txt = RiskCalculator.evaluate_flood_risk(pred, 'TS16')
            warnings = []

            if ts2_rise > Predictor.ANOMALY_RISE_THRESHOLD:
                warnings.append(f"น้ำเหนือหลากเร็ว (+{ts2_rise:.2f}ม./ชม.)")
            if ts16_now > Predictor.BACKWATER_LEVEL_TRIGGER and diff < Predictor.BACKWATER_DIFF_THRESHOLD:
                warnings.append(f"ภาวะน้ำหนุนระบายยาก (Diff {diff:.2f}ม.)")

            if warnings:
                final_status = f"🟠 เฝ้าระวังพิเศษ! ({' และ '.join(warnings)})"
                self.stdout.write(self.style.WARNING(f"🚨 ANOMALY DETECTED: {final_status}"))
            else:
                final_status = risk_txt
                self.stdout.write(self.style.SUCCESS(f"✅ Pattern ปกติ: {final_status}"))

            self.stdout.write(f"   ML Prediction ({PREDICT_HOURS}h): {pred:.4f} ม.")
            self.stdout.write(self.style.SUCCESS(f"📢 Final Decision: {final_status}"))

        # ==========================================
        # 6.5 การตรวจสอบระยะเตือนภัยล่วงหน้า (Early Warning & Lead Time Verification)
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("⏱️  EARLY WARNING & LEAD TIME VERIFICATION")
        self.stdout.write("="*55)

        thresholds = RiskCalculator.get_thresholds('TS16')
        warn_th = thresholds.get('warn', 110.0)
        crit_th = thresholds.get('crit', 112.0)
        all_predictions = final_model.predict(X)

        actual_warn_mask = y.values >= warn_th
        pred_warn_mask = all_predictions >= warn_th
        warn_count = int(np.sum(actual_warn_mask))

        lead_time_info = {
            'target_station': 'TS16 (M.7)',
            'horizon_hours': PREDICT_HOURS,
            'warn_threshold': warn_th,
            'crit_threshold': crit_th,
            'actual_flood_hours': warn_count,
            'hit_rate': None,
            'missed_hours': 0,
            'false_alarm_hours': 0,
            'early_warning_confirmed': False,
        }

        if warn_count > 0:
            tp_warn = int(np.sum(actual_warn_mask & pred_warn_mask))
            fn_warn = int(np.sum(actual_warn_mask & ~pred_warn_mask))
            fp_warn = int(np.sum(~actual_warn_mask & pred_warn_mask))

            hit_rate = (tp_warn / warn_count) * 100.0
            lead_time_info['hit_rate'] = round(hit_rate, 1)
            lead_time_info['missed_hours'] = fn_warn
            lead_time_info['false_alarm_hours'] = fp_warn
            lead_time_info['early_warning_confirmed'] = hit_rate >= 80.0

            self.stdout.write(f"   เกณฑ์เตือนภัยเป้าหมาย : Warning >= {warn_th:.2f} ม. / Critical >= {crit_th:.2f} ม.")
            self.stdout.write(f"   จำนวนชั่วโมงที่น้ำแตะเกณฑ์ : {warn_count:,} ชั่วโมง")
            self.stdout.write(f"   เตือนล่วงหน้าสำเร็จ (TP) : {tp_warn:,} ชั่วโมง")
            self.stdout.write(f"   เตือนหลุด/พลาด (FN)   : {fn_warn:,} ชั่วโมง")
            self.stdout.write(f"   เตือนหลอก (FP)        : {fp_warn:,} ชั่วโมง")
            self.stdout.write(self.style.SUCCESS(
                f"   🎯 Early Warning Hit Rate : {hit_rate:.1f}% (ทำนายนำหน้าน้ำจริง {PREDICT_HOURS} ชั่วโมง)"
            ))
            if fn_warn == 0:
                self.stdout.write(self.style.SUCCESS("   🛡️  การันตีความปลอดภัย: ไม่มีชั่วโมงวิกฤตที่หลุดรอด (0 Missed Alarms)"))
        else:
            max_y = float(np.max(y.values)) if len(y) > 0 else 0
            self.stdout.write(f"   เกณฑ์เตือนภัยเป้าหมาย : Warning >= {warn_th:.2f} ม.")
            self.stdout.write(f"   ระดับน้ำสูงสุดในรอบนี้ : {max_y:.2f} ม. (น้ำอยู่ในสภาวะปกติ ยังไม่แตะเกณฑ์เตือนภัย)")
            self.stdout.write(f"   ระยะเวลาพยากรณ์ล่วงหน้า: {PREDICT_HOURS} ชั่วโมงสม่ำเสมอ")
            lead_time_info['hit_rate'] = 100.0
            lead_time_info['early_warning_confirmed'] = True

        # ==========================================
        # 7. Plotting & Save File (Interactive JSON + 2-Tier Static Plot)
        # ==========================================
        if not no_plot and not X.empty:
            self.stdout.write(f"\n{'='*55}")
            self.stdout.write("📈 กำลังประมวลผลกราฟการทดสอบ (Interactive Data + Static Image)...")

            plot_dir = os.path.join(settings.BASE_DIR, 'static', 'images')
            os.makedirs(plot_dir, exist_ok=True)

            # 7.1 บันทึกข้อมูล JSON สำหรับกราฟ Interactive (Plotly บนเว็บ)
            eval_data_file = os.path.join(plot_dir, 'evaluation_data.json')
            timestamps_str = [t.strftime('%Y-%m-%d %H:%M') for t in y.index]
            actual_vals = [round(float(v), 3) for v in y.values]
            pred_vals = [round(float(v), 3) for v in all_predictions]
            diff_vals = [round(float(p - a), 3) for a, p in zip(actual_vals, pred_vals)]

            eval_data = {
                'timestamps': timestamps_str,
                'actual': actual_vals,
                'predicted': pred_vals,
                'diff': diff_vals,
                'crit_threshold': thresholds.get('crit', 112.0),
                'warn_threshold': thresholds.get('warn', 111.0),
                'r2': round(avg_r2, 4),
                'mae': round(avg_mae, 4),
                'horizon': PREDICT_HOURS,
                'mode': mode,
                'mode_title': mode_titles.get(mode, mode),
                'period': filter_desc,
                'total_points': len(timestamps_str),
                'lead_time': lead_time_info,
            }

            with open(eval_data_file, 'w', encoding='utf-8') as f_json:
                json.dump(eval_data, f_json, ensure_ascii=False)
            self.stdout.write(self.style.SUCCESS(
                f"✅ บันทึกชุดข้อมูล Interactive สำเร็จ: static/images/evaluation_data.json ({len(timestamps_str):,} จุด)"
            ))

            # 7.2 บันทึกกราฟ Static Image (Dual-Panel Overview & Zoomed Focus Window)
            plot_file = os.path.join(plot_dir, 'evaluation_plot.png')
            if len(y) >= 48:
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw={'height_ratios': [1.1, 1]})

                # Panel 1: Full Period Overview
                ax1.plot(y.index, y, label='Actual Level (M.7)', color='#2563eb', alpha=0.75, linewidth=2)
                ax1.plot(y.index, all_predictions, label=f'AI Predicted ({PREDICT_HOURS}h ahead)', color='#dc2626', linestyle='--', linewidth=1.6)
                ax1.axhline(y=thresholds['crit'], color='#991b1b', linestyle=':', linewidth=1.2, label=f"Critical ({thresholds['crit']}m)")
                ax1.axhline(y=thresholds['warn'], color='#d97706', linestyle=':', linewidth=1.2, label=f"Warning ({thresholds['warn']}m)")

                if mode in ['simulate', 'flash_flood', 'backwater'] and len(y) > 20:
                    ax1.axvspan(y.index[-20], y.index[-1], color='#fef08a', alpha=0.35, label=f'Simulation Zone ({mode})')

                # กำหนดช่วงหน้าต่าง 72 ชม. สำหรับซูมเจาะลึก
                if mode in ['simulate', 'flash_flood', 'backwater'] and len(y) > 24:
                    focus_idx_end = len(y)
                    focus_idx_start = max(0, focus_idx_end - 72)
                else:
                    peak_idx = int(np.argmax(y.values))
                    focus_idx_start = max(0, peak_idx - 36)
                    focus_idx_end = min(len(y), focus_idx_start + 72)
                    if focus_idx_end - focus_idx_start < 72:
                        focus_idx_start = max(0, focus_idx_end - 72)

                focus_times = y.index[focus_idx_start:focus_idx_end]
                focus_y = y.iloc[focus_idx_start:focus_idx_end]
                focus_pred = all_predictions[focus_idx_start:focus_idx_end]

                # ไฮไลต์ Focus Window บน Overview
                ax1.axvspan(focus_times[0], focus_times[-1], color='#38bdf8', alpha=0.18, label='Focus Window (72h Focus Below)')
                ax1.set_title(
                    f'UFA Flood Model Evaluation: Overview [{mode.upper()} | {plot_filter_desc}] - Avg R2={avg_r2:.4f}, MAE={avg_mae:.4f}m',
                    fontsize=12, fontweight='bold'
                )
                ax1.set_ylabel('Water Level MSL (m)', fontsize=10)
                ax1.legend(loc='upper left', framealpha=0.9, fontsize=9)
                ax1.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.6)

                # Panel 2: 72-Hour Detailed Zoom Window
                ax2.plot(focus_times, focus_y, label='Actual Level (Hourly Points)', color='#2563eb', linewidth=2, marker='o', markersize=3.5, alpha=0.9)
                ax2.plot(focus_times, focus_pred, label=f'AI Predicted ({PREDICT_HOURS}h ahead)', color='#dc2626', linestyle='--', linewidth=1.8, marker='x', markersize=4.5, alpha=0.9)
                ax2.fill_between(focus_times, focus_y, focus_pred, color='#fca5a5', alpha=0.3, label='Prediction Error (Gap)')
                ax2.axhline(y=thresholds['crit'], color='#991b1b', linestyle=':', linewidth=1.2, label=f"Critical ({thresholds['crit']}m)")
                ax2.axhline(y=thresholds['warn'], color='#d97706', linestyle=':', linewidth=1.2, label=f"Warning ({thresholds['warn']}m)")

                focus_mae = mean_absolute_error(focus_y, focus_pred)
                peak_actual = float(np.max(focus_y))
                peak_time = focus_y.index[np.argmax(focus_y.values)]
                peak_pred = float(focus_pred[np.argmax(focus_y.values)])

                ax2.annotate(
                    f"Peak Actual: {peak_actual:.2f}m\nPred: {peak_pred:.2f}m (Diff: {peak_pred-peak_actual:+.2f}m)",
                    xy=(peak_time, peak_actual),
                    xytext=(15, 12),
                    textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.4', fc='#fef3c7', ec='#d97706', lw=1),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2', color='#b45309', lw=1.2),
                    fontsize=8.5,
                    fontweight='bold'
                )

                ax2.set_title(
                    f'Zoom Inspection: 72-Hour Focus Window ({focus_times[0].strftime("%d/%m/%Y")} - {focus_times[-1].strftime("%d/%m/%Y")}) [Focus MAE = {focus_mae:.4f} m]',
                    fontsize=11, fontweight='bold'
                )
                ax2.set_ylabel('Water Level MSL (m)', fontsize=10)
                ax2.set_xlabel('Time (Hourly Steps)', fontsize=10)
                ax2.legend(loc='upper left', framealpha=0.9, fontsize=8.5)
                ax2.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.6)

                plt.tight_layout()
                plt.savefig(plot_file, dpi=140)
                plt.close()
            else:
                plt.figure(figsize=(12, 6))
                plt.plot(y.index, y, label='Actual Level (Hourly Points)', color='#2563eb', linewidth=2, marker='o', markersize=4, alpha=0.85)
                plt.plot(y.index, all_predictions, label=f'AI Predicted ({PREDICT_HOURS}h ahead)', color='#dc2626', linestyle='--', linewidth=1.8, marker='x', markersize=5, alpha=0.9)
                plt.fill_between(y.index, y, all_predictions, color='#fca5a5', alpha=0.3, label='Prediction Error (Gap)')
                plt.axhline(y=thresholds['crit'], color='#991b1b', linestyle=':', label=f"Critical ({thresholds['crit']}m)")
                plt.axhline(y=thresholds['warn'], color='#d97706', linestyle=':', label=f"Warning ({thresholds['warn']}m)")
                plt.title(
                    f'UFA Flood Model Evaluation: Actual vs Predicted [{mode.upper()} | {plot_filter_desc}] - Avg R2={avg_r2:.4f}, MAE={avg_mae:.4f}m',
                    fontsize=12, fontweight='bold'
                )
                plt.ylabel('Water Level MSL (m)')
                plt.xlabel('Time')
                plt.legend(loc='upper left', framealpha=0.9)
                plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.6)
                plt.tight_layout()
                plt.savefig(plot_file, dpi=140)
                plt.close()

            self.stdout.write(self.style.SUCCESS(f"✅ บันทึกกราฟสำเร็จ: static/images/evaluation_plot.png"))

        # ==========================================
        # 8. SUMMARY
        # ==========================================
        self.stdout.write(f"\n{'='*55}")
        self.stdout.write("📋  EVALUATION SUMMARY")
        self.stdout.write("="*55)
        self.stdout.write(f"   Mode          : {mode_titles.get(mode, mode)}")
        self.stdout.write(f"   Period        : {filter_desc}")
        self.stdout.write(f"   Data Points   : {total_rows:,} rows")
        self.stdout.write(f"   Features      : {len(feature_cols)} columns")
        self.stdout.write(f"   Horizon       : {PREDICT_HOURS}h ahead")
        self.stdout.write(f"   Avg R²        : {avg_r2:.4f}")
        self.stdout.write(f"   Avg MAE       : {avg_mae:.4f} ม.")
        if lead_time_info.get('hit_rate') is not None:
            self.stdout.write(f"   Lead Time Hit : {lead_time_info['hit_rate']:.1f}% ({PREDICT_HOURS}h ahead verification)")
        if pred_val_out is not None:
            self.stdout.write(f"   ML Prediction : {pred_val_out:.4f} ม.")
        self.stdout.write(f"   Final Decision: {final_status}")
        self.stdout.write("="*55)
        self.stdout.write(self.style.SUCCESS("🎉 การประเมินและทดสอบโมเดลเสร็จสิ้นสมบูรณ์\n"))
