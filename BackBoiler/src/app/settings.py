
from pathlib import Path
import os


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-gd)b6%djxlp0g1zw#@5v3_w#d%pu4%g7)-!288)@m(1kz*w+n6'


ALLOWED_HOSTS = ['79.175.177.113']

APP_NAME = 'backboiler'
APP_URL = 'http://127.0.0.1:8000'


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

APP_NAME = 'backboiler'
APP_URL = 'http://127.0.0.1:8000'



# transltations 
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Set default language
LANGUAGE_CODE = 'en'
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
    # 'django-jalali-date',
    'jalali_date',
    'django_browser_reload',
    'RateLimitModel',
    'ConnectModel',
    'LogModel',
    'UserModel',
    'AuthModel',
    'SsoModel',    
    'ui',
    'News_Picture_Generator',
    'Translate'
    
]

# CORS Headers

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost',
    'http://79.175.177.113:16300',
]
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost',
]
CORS_ALLOW_HEADERS = [ "accept", "referer", "accept-encoding", "authorization", "content-type", "dnt", "origin", "user-agent", "x-csrftoken", "x-sessionid", "x-requested-with"]
CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'OPTIONS',
]

CORS_ALLOW_CREDENTIALS = True

# Tailwind Settings
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = [
    "127.0.0.1",
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
    'LogModel.log_handler.drf_ExceptionMiddleware',
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
                'django.template.context_processors.i18n',
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

STATIC_URL = '/static'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'LogModel.log_handler.request_processing_exception_handler'
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'BackBoiler Model API',
    'DESCRIPTION': 'BackBoiler framework for every Django Project needs.',
    'VERSION': '1.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'PREPROCESSING_HOOKS': ['app.swagger_schema.preprocessing_filter_spec']
}




# STATICFILES_DIRS = [
#     BASE_DIR / "static",
#     BASE_DIR / "ui" /"static",
    
# ]

# If you're using collectstatic for production
# STATIC_ROOT = BASE_DIR / "staticfiles"
