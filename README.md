# UFA Flood Alert (UFAsite)

Django web application for monitoring water levels (EGAT WaterTele), storing measurements in MySQL, calculating flood risk, and sending LINE notifications.

## Tech Stack

- Python / Django
- MySQL
- Data scraping: `requests`, `beautifulsoup4`
- Optional tunneling for webhooks/demo: `ngrok`
- LINE Messaging API (multicast alerts)

## Project Structure (high level)

- `UFAsite/` – Django project root
  - `manage.py` – Django management entry point
  - `UFAsite/` – Django settings/urls/asgi/wsgi
  - `pages/` – main app (models, views, risk logic, utilities)
    - `management/commands/scrape_data.py` – custom command to scrape EGAT station data
  - `templates/` – HTML templates
  - `static/` – static assets (images/css/js)

## Prerequisites

- Python 3.x
- MySQL Server running locally (default config in this repo uses `127.0.0.1:3306`)
- (Recommended) virtual environment

## Setup

### 1) Create & activate a virtual environment

Windows (cmd/PowerShell):

```bat
python -m venv venv
venv\Scripts\activate
```

### 2) Install dependencies

If you already have a `requirements.txt`, install from it:

```bat
pip install -r requirements.txt
```

If you **do not** have a `requirements.txt`, install the typical dependencies used by this project:

```bat
pip install django mysqlclient requests beautifulsoup4
```

> Note: `mysqlclient` may require build tools on Windows. If you run into issues, install the appropriate Visual C++ build tools or use an alternative MySQL driver and update Django `DATABASES` accordingly.

### 3) Configure the database

This project is configured for MySQL in `UFAsite/UFAsite/settings.py`:

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

Create the database in MySQL:

```sql
CREATE DATABASE ubon_flood_alert CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Then apply migrations:

```bat
python UFAsite\manage.py migrate
```

### 4) Configure LINE Messaging API (optional)

LINE credentials are currently stored in `UFAsite/UFAsite/settings.py`:

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`

For security, prefer moving these to environment variables for real deployments.

## Running the App

From the repository root:

```bat
python UFAsite\manage.py runserver
```

Open:

- http://127.0.0.1:8000/

## Key Commands (used in this project)

Activate venv:

```bat
venv\Scripts\activate
```

Scrape and store water level data (custom management command):

```bat
python UFAsite\manage.py scrape_data
```

Run tests for the `pages` app:

```bat
python UFAsite\manage.py test pages
```

Run ngrok (to expose port 8000):

```bat
ngrok http 8000
```

## Scraping & Risk Evaluation Notes

- The scraper pulls station data from EGAT WaterTele using an AJAX endpoint and parses hidden `<input>` values such as `waterLV` and `date`.
- Risk is evaluated via `pages/risk_calculator.py`.
- Alerts (when enabled) are sent via `pages/utils.py` (multicast) and are currently triggered only for station `TS16` when `risk_level > 0`.

## Security Notes

This repository currently contains sensitive values in source control (e.g., Django `SECRET_KEY`, MySQL password, LINE tokens). For production:

- Move secrets to environment variables or a secret manager
- Restrict `ALLOWED_HOSTS` (do not use `'*'`)
- Disable `DEBUG`

## License

Add your license information here.
