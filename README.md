# UFA Flood Alert (UFAsite)

Django web application for monitoring water levels (**ThaiWater API**), storing measurements in **TiDB (MySQL-compatible)**, calculating flood risk with a **Hybrid Prediction System (AI + Rules)**, and sending LINE notifications.

## Project Location

- Root path: `d:\Coding\Final Project`
- Django manage script: `UFAsite\manage.py`

## Key Features

- **Real-time Data:** Scrape latest water levels from **ThaiWater API** for stations:
  - **TS2** (M.5 Rasidalai - Upstream)
  - **TS16** (M.7 Ubon City - Critical Point)
  - **TS5** (M.11B Kaeng Saphoe - Downstream)
- **Automated Data Updates:** **GitHub Actions** workflow runs every 15 minutes to fetch new data automatically.
- **Database:** Persist data to **TiDB Serverless** (Production) / Local MySQL (Dev).
- **Hybrid Risk Evaluation:**
  - **Rule-based:** Immediate alert based on station thresholds.
  - **AI Prediction:** Linear Regression model predicts water level 6 hours ahead.
  - **Anomaly Detection:** Detects Flash Floods (rapid rise) and Backwater Effects.
- **Flood Simulation:** Built-in module to simulate flood scenarios and test the alert system.
- **LINE Messaging integration:** subscribe/unsubscribe, quick replies to query station status, emergency contacts Flex Message.

## Tech Stack & Dependencies

- **Backend:** Python / Django 5.x
- **Database:** TiDB (Production), MySQL (Development) - using `mysqlclient`
- **Data Fetching:** `requests`, `beautifulsoup4` (ThaiWater API)
- **Automation:** GitHub Actions (Cron Job)
- **LINE API:** `line-bot-sdk`
- **ML & Science:** `pandas`, `scikit-learn`, `joblib`, `numpy`, `matplotlib`
- **Deployment:** Render (Web Service)

## Project Structure (high level)

- `UFAsite/` – Django project root
  - `manage.py` – Django management entry point
  - `UFAsite/` – Django settings/urls/asgi/wsgi
  - `pages/` – main app
    - `management/commands/scrape_data.py` – **Fetch data from ThaiWater API**
    - `management/commands/train_model.py` – Train & save ML model
    - `management/commands/simulation.py` – **Run flood simulation & hybrid system test**
    - `risk_calculator.py` – Thresholds + rule-based evaluation
    - `predictor.py` – **Hybrid Prediction Logic (ML + Anomaly Rules)**
    - `views.py` – Web views + LINE webhook handlers
  - `.github/workflows/scraper.yml` – **GitHub Actions Scheduler**

## Endpoints

- `GET /` – Home page showing latest levels.
- `POST /webhook/` – LINE webhook endpoint.

## Quick Start (Windows)

```bat
cd /d d:\Coding\Final Project
python -m venv venv
venv\Scripts\activate

:: Install dependencies
pip install -r requirements.txt
```

Create DB and apply migrations:

```bat
# Ensure you have MySQL running locally for dev
python UFAsite\manage.py migrate
```

Run the development server:

```bat
python UFAsite\manage.py runserver
```

Open: http://127.0.0.1:8000/

## Configuration

Database (`UFAsite/UFAsite/settings.py`):
- **Development**: Uses local MySQL (`root` user).
- **Production (Render)**: Uses **TiDB Serverless** via Environment Variables:
  - `TIDB_HOST`, `TIDB_PORT`, `TIDB_USER`, `TIDB_PASSWORD`, `TIDB_DATABASE`

## Data Flow

- **Automation:** GitHub Actions workflow (`scraper.yml`) triggers `scrape_data` command every 15 minutes.
- **Manual Scraper command:** `python UFAsite\manage.py scrape_data`
  - Pulls JSON data from ThaiWater API V3.
  - Maps Station Codes (M.7 -> TS16, etc.).
  - Saves to DB and evaluates risk.
  - Sends LINE Multicast alert if Critical.

## Machine Learning & Simulation

### 1. Train Model
```bat
python UFAsite\manage.py train_model
```
Trains a Linear Regression model using lagged features (1h, 2h, 3h) from all 3 stations to predict TS16 level 6 hours ahead.

### 2. Run Simulation
```bat
python UFAsite\manage.py simulation
```
- Simulates a synthesized flood wave on historical data.
- Tests the **Hybrid Prediction System**:
  1.  **ML Model**: Predicts basic trend.
  2.  **Flash Flood Rule**: Checks if upstream (TS2) rises > 0.5m/hr.
  3.  **Backwater Rule**: Checks if TS16 is high (>109m) but diff with TS5 is low (<1.5m).
- Generates a plot `Water Level Prediction: Full Timeline Simulation`.

## LINE Bot Usage

- Webhook: `/webhook/` (Requires HTTPS/ngrok)
- **Features:**
  - `รับการแจ้งเตือน` / `ยกเลิกการแจ้งเตือน`
  - `สถานะน้ำ` -> Quick Reply Menu
  - `ดู M.7` -> Real-time status
  - `คาดการณ์ล่วงหน้า` -> **Runs Hybrid Prediction (ML + Rules)**
  - `ข้อมูลติดต่อฉุกเฉิน` -> Flex Message

## Common Commands

```bat
:: Activate venv
venv\Scripts\activate

:: Run server
python UFAsite\manage.py runserver

:: Manual Data Fetch
python UFAsite\manage.py scrape_data

:: Run Flood Simulation
python UFAsite\manage.py simulation

:: Train ML Model
python UFAsite\manage.py train_model

:: Test Pages App
python UFAsite\manage.py test pages

:: Expose locally
ngrok http 8000
```

## Security & Deployment

- **Secrets**: Never commit `SECRET_KEY`, Database passwords, or LINE Tokens. Use `.env` or System Environment Variables.
- **Render Deployment**:
  - Build Command: `./UFAsite/build.sh`
  - Start Command: `gunicorn UFAsite.wsgi:application`
  - **Environment Variables Required**:
    - `django_settings_module`: `UFAsite.settings`
    - `SECRET_KEY`: (Your secret)
    - `TIDB_*`: (Database credentials)
    - `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`

## License

By Aphirat Niyom & Gemini
