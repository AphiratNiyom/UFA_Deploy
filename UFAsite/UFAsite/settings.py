from pathlib import Path
import os
import dj_database_url
import pymysql

pymysql.install_as_MySQLdb()
import MySQLdb
# Monkey-patch version to satisfy Django 5.x requirements
if hasattr(MySQLdb, 'version_info'):
    MySQLdb.version_info = (2, 2, 1, 'final', 0)
    MySQLdb.version = "2.2.1"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
for env_candidate in (BASE_DIR / '.env', BASE_DIR.parent / '.env'):
    if env_candidate.exists():
        with open(env_candidate, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        break


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-!)du$b&m06=2$pz@7n1uz6ma5)xq)xltdpe#w!)o_-@zr!w9rh')

# SECURITY WARNING: don't run with debug turned on in production!
if 'RENDER' in os.environ:
    DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
else:
    DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 't')

# อนุญาตให้เข้าถึงจากโดเมนของ Render และ localhost
allowed_hosts_str = os.environ.get('ALLOWED_HOSTS', 'ufa-deploy.onrender.com,localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_str.split(',') if h.strip()]
if DEBUG:
    for local_host in ('localhost', '127.0.0.1', '[::1]', 'testserver'):
        if local_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(local_host)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ย้ายขึ้นมาหลัง SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'UFAsite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'UFAsite.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

if 'RENDER' in os.environ:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('TIDB_DATABASE', 'ubon_flood_alert'),
            'USER': os.environ.get('TIDB_USER'),
            'PASSWORD': os.environ.get('TIDB_PASSWORD'),
            'HOST': os.environ.get('TIDB_HOST'),
            'PORT': os.environ.get('TIDB_PORT', '4000'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'ssl': {'fake_flag_to_enable_tls': True},
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else: 
    # ตั้งค่าสำหรับ Local Development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('LOCAL_DB_NAME', 'ubon_flood_alert'),
            'USER': os.environ.get('LOCAL_DB_USER', 'root'),
            'PASSWORD': os.environ.get('LOCAL_DB_PASSWORD', 'Apirat2018'),
            'HOST': os.environ.get('LOCAL_DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('LOCAL_DB_PORT', '3306'),   
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Bangkok'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# LINE BOT CONFIGURATION
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Custom Admin Panel Password
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'ufa-admin-2024')
