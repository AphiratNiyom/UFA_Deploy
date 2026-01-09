import pandas as pd
import numpy as np
import joblib
from datetime import timedelta
from django.utils import timezone

from .models import WaterLevels
from .risk_calculator import evaluate_flood_risk
from sklearn.linear_model import LinearRegression

# --- Constants ---
# Path to save the trained model
MODEL_PATH = 'trained_model.joblib' 
# How many hours into the future to predict
PREDICT_HOURS = 6
# Stations used for features
STATIONS_FOR_FEATURES = ['TS2', 'TS16', 'TS5']
# The station we are trying to predict
TARGET_STATION = 'TS16'
# List of feature names the model expects
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

    # Ensure all required station columns exist, fill with NaN if not
    for station in STATIONS_FOR_FEATURES:
        if station not in df.columns:
            df[station] = np.nan

    df = df.resample('h').mean()
    
    # Interpolate can fail if all values are NaN (e.g., new station).
    # We interpolate existing data, then fill remaining NaNs (at ends)
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
    """
    Fetches all historical data, trains a new prediction model,
    and saves it to a file specified by MODEL_PATH.
    """
    print("🔄 Starting model training process...")

    # 1. Fetch and prepare data
    print("   - Fetching data from database...")
    qs = WaterLevels.objects.all().values('recorded_at', 'station__station_id', 'water_level')
    if not qs.exists():
        print("❌ No data in database to train on. Aborting.")
        return

    df_raw = pd.DataFrame(qs)
    df = _prepare_dataframe(df_raw)

    if df.empty:
        print("❌ Data is empty after processing. Cannot train model.")
        return

    # 2. Create Target Variable
    df['target'] = df[TARGET_STATION].shift(-PREDICT_HOURS)
    df.dropna(inplace=True)

    if df.empty:
        print("❌ Data is empty after creating target. Not enough data to look ahead. Cannot train model.")
        return

    X = df[FEATURES_TO_USE]
    y = df['target']

    # 3. Train Model
    print(f"   - Training LinearRegression model on {len(X)} samples...")
    model = LinearRegression()
    model.fit(X, y)

    # 4. Save Model
    print(f"   - Saving model to {MODEL_PATH}...")
    joblib.dump(model, MODEL_PATH)

    print("✅ Model training complete.")
    return MODEL_PATH


def load_and_predict():
    """
    Loads the trained model, fetches the latest data to build a feature vector,
    and returns a prediction for the next N hours.
    
    Returns:
        A tuple of (predicted_level, risk_level, risk_text)
        Returns (None, None, "ข้อความแสดงข้อผิดพลาด") if prediction fails.
    """
    # 1. Load the model
    try:
        model = joblib.load(MODEL_PATH)
    except FileNotFoundError:
        return None, None, f"ไม่พบไฟล์โมเดล ({MODEL_PATH}) กรุณารันคำสั่ง train_model ก่อน"

    # 2. Fetch recent data to build the feature vector
    # We need at least 3-4 hours of data to create the lags. Fetch last 12 hours to be safe.
    now = timezone.now()
    start_time = now - timedelta(hours=12)
    
    qs = WaterLevels.objects.filter(
        station__station_id__in=STATIONS_FOR_FEATURES,
        recorded_at__gte=start_time
    ).values('recorded_at', 'station__station_id', 'water_level')

    if not qs.exists():
        return None, None, "ไม่พบข้อมูลล่าสุดสำหรับใช้ในการทำนาย"

    # 3. Prepare data and get the last valid row for prediction
    df_raw = pd.DataFrame(qs)
    df_processed = _prepare_dataframe(df_raw)

    if df_processed.empty or not all(f in df_processed.columns for f in FEATURES_TO_USE):
         return None, None, "ข้อมูลล่าสุดไม่เพียงพอสำหรับสร้าง Feature ในการทำนาย"

    # Get the last row as our input vector
    input_vector = df_processed[FEATURES_TO_USE].tail(1)

    # 4. Predict
    predicted_level = model.predict(input_vector)[0]
    
    # 5. Evaluate risk
    risk_level, risk_text = evaluate_flood_risk(predicted_level, station_id=TARGET_STATION)
    
    return predicted_level, risk_level, risk_text
