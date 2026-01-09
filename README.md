# UFA Flood Alert (UFAsite)

Django web application for monitoring water levels (EGAT WaterTele), storing measurements in MySQL, calculating flood risk, training a simple ML model, and sending LINE notifications.

## Project Location

- Root path: `d:\Coding\Final Project`
- Django manage script: `UFAsite\manage.py`

## Key Features

- Scrape latest water levels for EGAT stations (TS2/M.5, TS16/M.7, TS5/M.11B)
- Persist data to MySQL
- Rule-based risk evaluation by station thresholds
- LINE Messaging integration: subscribe/unsubscribe, quick replies to query station status, emergency contacts Flex Message
- Train a basic ML model (RandomForest) for risk_level prediction based on collected data

## Tech Stack & Dependencies

- Python / Django
- MySQL (django backend: `mysqlclient`)
- Data scraping: `requests`, `beautifulsoup4`
- LINE Messaging API SDK: `line-bot-sdk`
- ML training: `pandas`, `scikit-learn`, `joblib`
- Optional tunneling: `ngrok`

## Project Structure (high level)

- `UFAsite/` – Django project root
  - `manage.py` – Django management entry point
  - `UFAsite/` – Django settings/urls/asgi/wsgi
  - `pages/` – main app
    - `management/commands/scrape_data.py` – scrape EGAT station data
    - `management/commands/train_model.py` – train & save ML model
    - `risk_calculator.py` – thresholds + rule-based risk evaluation
    - `utils.py` – LINE multicast helpers, etc.
    - `views.py` – home page + LINE webhook handlers
    - `urls.py` – routes (`/`, `/webhook/`)
  - `templates/` – HTML templates (e.g., `home.html`)
  - `static/` – static assets
- `คำสั่งในการใช้งาน.txt` – Thai quick usage notes

## Endpoints

- `GET /` – Home page showing latest levels for TS2 (M.5), TS16 (M.7), TS5 (M.11B)
- `POST /webhook/` – LINE webhook endpoint

## Quick Start (Windows)

```bat
cd /d d:\Coding\Final Project
python -m venv venv
venv\Scripts\activate

:: Install dependencies (use requirements.txt if present)
pip install -r requirements.txt
:: If you do not have requirements.txt:
pip install django mysqlclient requests beautifulsoup4 line-bot-sdk pandas scikit-learn joblib
```

Create DB and apply migrations:

```sql
-- In MySQL
CREATE DATABASE ubon_flood_alert CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bat
python UFAsite\manage.py migrate
```

Run the development server:

```bat
python UFAsite\manage.py runserver
```

Open: http://127.0.0.1:8000/

## Configuration

Database (`UFAsite/UFAsite/settings.py`):

```python
DATABASES = {
  'default': {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'ubon_flood_alert',
    'USER': 'root',
    'PASSWORD': '...your password...',
    'HOST': '127.0.0.1',
    'PORT': '3306',
  }
}
```

LINE Messaging API (used in `pages.views`):

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`

For production, move these to environment variables and do not commit secrets.

## Data Flow

- Scraper command: `python UFAsite\manage.py scrape_data`
  - Pulls stations TS2 (M.5), TS16 (M.7), TS5 (M.11B)
  - Parses `waterLV` and `date` from EGAT WaterTele AJAX (hidden inputs)
  - Converts BE to AD, stores to DB
  - Evaluates risk via `evaluate_flood_risk`
  - Sends multicast alert for TS16 when `risk_level > 0`
- Home page (`/`) queries the latest record per station and displays status

## Machine Learning Model

- Training command:

```bat
python UFAsite\manage.py train_model
```

- What it does:
  - Loads water level data from DB (uses features like `water_level`, target `risk_level`)
  - Splits data (train/test), trains `RandomForestClassifier`
  - Prints accuracy on the test split
  - Saves model to: `UFAsite\pages\predictor_model.joblib`

- Requirements: `pandas`, `scikit-learn`, `joblib`
- Needs at least a few rows of data in `WaterLevels` to train (command will stop if insufficient)

## LINE Bot Usage

- Webhook: `/webhook/`
- Supported messages:
  - `รับการแจ้งเตือน` – subscribe
  - `ยกเลิกการแจ้งเตือน` – unsubscribe
  - `สถานะน้ำ` / `สถานะน้ำปัจจุบัน` / `ดูระดับน้ำ` – show Quick Reply to choose a station
  - `ดู M.5` / `ดู M.7` / `ดู M.11B` – return the latest status for that station
  - `ข้อมูลติดต่อฉุกเฉิน` – send Flex Message with emergency contacts

Expose webhook locally:

```bat
ngrok http 8000
```

Use ngrok HTTPS URL + `/webhook/` in LINE developer console. During development `ALLOWED_HOSTS = ['*']` is set; restrict in production.

## Common Commands

```bat
:: Activate venv
cd /d d:\Coding\Final Project
venv\Scripts\activate

:: Run server
python UFAsite\manage.py runserver

:: Scrape data
python UFAsite\manage.py scrape_data

:: Train ML model
python UFAsite\manage.py train_model

:: Run tests for pages app
python UFAsite\manage.py test pages

:: Expose locally
ngrok http 8000
```

## Security Notes

- Do not commit secrets (Django `SECRET_KEY`, DB password, LINE tokens)
- Set `DEBUG = False` and restrict `ALLOWED_HOSTS` for production
- Prefer environment variables or a secrets manager

## Troubleshooting

- `mysqlclient` on Windows may require Microsoft Visual C++ Build Tools
- If webhook returns `403` or signature errors, verify `LINE_CHANNEL_SECRET` and request signatures
- If ngrok URL changes, update LINE webhook URL

## สรุปคำสั่งใช้งาน (ภาษาไทย)

- เปิดสภาพแวดล้อม: `venv\Scripts\activate`
- ดึงข้อมูล: `python UFAsite\manage.py scrape_data`
- เทสระบบ: `python UFAsite\manage.py test pages`
- ฝึกสอนโมเดล: `python UFAsite\manage.py train_model`
- เปิดเผยพอร์ตผ่านอินเทอร์เน็ต: `ngrok http 8000`

## License

Add your license information here.
