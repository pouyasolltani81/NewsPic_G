
from pathlib import Path
import os

# Import config utilities first
from .config_utils import get_project_name, get_display_name, get_project_description, get_ui_theme, get_default_language, get_supported_languages, is_analytics_enabled, get_analytics_sample_rate, is_debug_enabled, get_allowed_hosts , get_project_version , get_cors_enabled , get_csrf_enabled

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-gd)b6%djxlp0g1zw#@5v3_w#d%pu4%g7)-!288)@m(1kz*w+n6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = is_debug_enabled()

ALLOWED_HOSTS = get_allowed_hosts()

APP_NAME = get_project_name()
APP_URL = 'http://79.175.177.113:19800'





# Analytics Configuration
ANALYTICS_ENABLED = is_analytics_enabled()
ANALYTICS_SAMPLE_RATE = get_analytics_sample_rate()

# GeoIP settings (only if enabled)
if is_analytics_enabled():
    GEOIP_PATH = os.path.join(BASE_DIR, 'geoip')
else:
    GEOIP_PATH = None

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# # Celery settings (optional, for async processing)
# CELERY_BROKER_URL = 'redis://localhost:6379/0'
# CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# transltations 
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Set default language
LANGUAGE_CODE = get_default_language()
USE_I18N = True
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGES = [
    ('en', 'English'),
    ('fa', 'فارسی'),
]

LANGUAGE_COOKIE_NAME = 'django_language'

# Path to your translation files
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'drf_spectacular',
    'corsheaders',
    'rest_framework',
    'tailwind',
    'theme',
    'django_browser_reload',
    'RateLimitModel',
    'ConnectModel',
    'LogModel',
    'UserModel',
    'AuthModel',
    'SsoModel',    
    'UI',
    'AnalyticsModel',
    'News_Picture_Generator',
    'Translate'

]


# =========================================
# CORS Headers
# =========================================
if get_cors_enabled():
    CORS_ORIGIN_ALLOW_ALL = False
    CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost',
    'http://localhost:8000',
    'http://79.175.177.113',
    'http://79.175.177.113:8000',
    'http://79.175.177.113:20300',
    'https://79.175.177.113:20300',
    'http://5.232.48.6',
    'http://2.180.249.205',
    'http://79.175.177.113:16300',
    'http://79.175.177.113:24300',
    'http://localhost:3333',
    'http://217.219.245.139',
    'http://217.219.245.139:20300',
    'http://aimoonhub.ir:20300',
    'https://aimoonhub.ir:20300',
    'http://aimoonhub.ir',
    'https://aimoonhub.ir',
    'https://news.imoonex.ir',
    "https://aimoonhub.imoonex.ir",
    "https://aimoonhub.ir",
    "https://aimoonhub.com",
    'http://79.175.177.113:29300',   
    'https://79.175.177.113:29800', 
    'http://aimoonhub.ir:29300', 
    'https://aimoonhub.ir:29800',
    'http://5.125.28.18:3333',
    'https://news.imoonex.ir',
    'http://news.imoonex.ir',
    #'http://5.126.123.184/3000'
    ]
    
    CORS_ALLOW_HEADERS = [ "accept", "referer", "accept-encoding", "authorization", "content-type", "dnt", "origin", "user-agent", "x-csrftoken", "x-sessionid", "x-requested-with"]
    CORS_ALLOW_METHODS = [
        'GET',
        'POST',
        'OPTIONS',
    ]
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ORIGIN_ALLOW_ALL = False
    CORS_ALLOWED_ORIGINS = []
    CORS_ALLOW_HEADERS = []
    CORS_ALLOW_METHODS = []
    CORS_ALLOW_CREDENTIALS = False


# =========================================
# CSRF Settings
# =========================================
if get_csrf_enabled():
    CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost',
    'http://localhost:8000',
    'http://79.175.177.113',
    'http://79.175.177.113:8000',
    'http://79.175.177.113:20300',
    'https://79.175.177.113:20300',
    'http://5.232.48.6',
    'http://2.180.249.205',
    'http://79.175.177.113:16300',
    'http://79.175.177.113:24300',
    'http://localhost:3333',
    'http://217.219.245.139',
    'http://217.219.245.139:20300',
    'http://79.175.177.113:29300',   
    'https://79.175.177.113:29800', 
    'http://aimoonhub.ir:29300', 
    'https://aimoonhub.ir:29800',
    'http://aimoonhub.ir:20300', 
    'https://aimoonhub.ir:20300',
    'http://aimoonhub.ir',
    'https://aimoonhub.ir',
    'https://news.imoonex.ir',
    'http://news.imoonex.ir',
    "https://aimoonhub.imoonex.ir",
    "https://aimoonhub.ir",
    "https://aimoonhub.com",
    'http://5.125.28.18:3333'
    ]

    CSRF_COOKIE_SECURE = True   # Only over HTTPS
    CSRF_COOKIE_HTTPONLY = True
    CSRF_USE_SESSIONS = False   # Optional: depends on your setup
else:
    # Disable CSRF protection (⚠️ only safe for local/dev use!)
    CSRF_TRUSTED_ORIGINS = []
    CSRF_COOKIE_SECURE = False
    CSRF_COOKIE_HTTPONLY = False
    CSRF_USE_SESSIONS = False


# Tailwind Settings
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = [
    "127.0.0.1",
    "79.175.177.113"
]
# NPM_BIN_PATH = 'C:/Program Files/nodejs/npm.cmd'
from .app_lib import Find_npm_bin
NPM_BIN_PATH = Find_npm_bin()
#####

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    'LogModel.log_handler.DRFExceptionMiddleware',
    'AnalyticsModel.middleware.AnalyticsMiddleware', 

]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'dbs/') + 'main.sqlite3',

    },
    'Logs': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'dbs/') + 'Logs.sqlite3',
    },
}

AUTH_USER_MODEL = 'UserModel.User'

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

# TIME_ZONE = 'UTC'
TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'LogModel.log_handler.request_processing_exception_handler'
}

SPECTACULAR_SETTINGS = {
    'TITLE': f'{get_display_name()}',
    'DESCRIPTION': f'{get_project_description()}',
    'VERSION': f'{get_project_version()}',
    'SERVE_INCLUDE_SCHEMA': False,
    'PREPROCESSING_HOOKS': ['app.swagger_schema.preprocessing_filter_spec']
}




# logging 
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": "WARNING",  
            "propagate": False,
        },
    },
}



TRANSLATE_API_URL = 'http://79.175.177.113:19800/Translate/translate/'
