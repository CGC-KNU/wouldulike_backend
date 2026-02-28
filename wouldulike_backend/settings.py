from pathlib import Path
import os, json, environ
from django.core.exceptions import ImproperlyConfigured
from decouple import config

import urllib.parse


BASE_DIR = Path(__file__).resolve().parent.parent


# .env 파일 로드
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

USE_LOCAL_SQLITE = os.getenv("DJANGO_USE_LOCAL_SQLITE", "0") == "1"
DISABLE_EXTERNAL_DBS = os.getenv("DJANGO_DISABLE_EXTERNAL_DBS", "0") == "1"


secret_file = os.path.join(BASE_DIR, 'secrets.json')  # secrets.json 파일 위치를 명시

with open(secret_file) as f:
    secrets = json.loads(f.read())

def get_secret(setting):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        raise ImproperlyConfigured(error_msg)

SECRET_KEY = os.getenv("SECRET_KEY")


DEBUG = config('DEBUG', default=True, cast=bool)


ALLOWED_HOSTS = ['*']
# ALLOWED_HOSTS = ['deliberate-lenette-coggiri-5ee7b85e.koyeb.app', 'localhost', '127.0.0.1']

# URL 룰에서 트레일링 슬래시 자동 보정
APPEND_SLASH = True

# CORS 설정
CORS_ALLOW_ALL_ORIGINS = True  # 개발 중 모든 도메인 허용
# 배포 시 특정 도메인만 허용하려면 아래 주석을 해제하고 CORS_ALLOW_ALL_ORIGINS를 False로 설정
# CORS_ALLOW_ALL_ORIGINS = False
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
#     # 프로덕션 도메인 추가
# ]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


AUTHENTICATION_FORM = 'guests.forms.CustomAuthenticationForm'


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'guests',
    'trends',
    'type_description',
    'food_by_type',
    'restaurants',
    'campus_restaurants',
    'notifications',
    'rest_framework',
    'corsheaders',
    'storages',
    'accounts',
    'coupons',
    'rest_framework_simplejwt.token_blacklist',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'wouldulike_backend.middleware.RequestLifecycleLoggingMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')


ROOT_URLCONF = 'wouldulike_backend.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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


WSGI_APPLICATION = 'wouldulike_backend.wsgi.application'


DATABASES = {
    'default': {   
        # 사용자 데이터베이스
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('default_db_name'),
        'USER': os.getenv('default_db_user'),
        'PASSWORD': os.getenv('default_db_password'),
        'HOST': os.getenv('default_db_host'),
        'PORT': os.getenv('default_db_port'),
    },
    'rds': {
        # 유형 데이터베이스
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('rds_db_name'),
        'USER': os.getenv('rds_db_user'),
        'PASSWORD': os.getenv('rds_db_password'),
        'HOST': os.getenv('rds_db_host'),
        'PORT': os.getenv('rds_db_port'),
        'OPTIONS': {
            'options': '-c client_encoding=utf8',
        },
    },
    'cloudsql': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('cloudsql_db_name'),
        'USER': os.getenv('cloudsql_db_user'),
        'PASSWORD': os.getenv('cloudsql_db_password'),
        'HOST': os.getenv('cloudsql_db_host'),
        'PORT': os.getenv('cloudsql_db_port'),
    }
}



DEFAULT_DB_CONFIG = DATABASES.get("default", {}).copy()

if USE_LOCAL_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "local.sqlite3"),
        }
    }
elif DISABLE_EXTERNAL_DBS:
    DATABASES = {
        "default": DEFAULT_DB_CONFIG,
    }

if USE_LOCAL_SQLITE or DISABLE_EXTERNAL_DBS:
    DATABASE_ROUTERS = []
else:
    DATABASE_ROUTERS = ['wouldulike_backend.db_routers.TypeDescriptionRouter']


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL"),  # redis://username:password@host:port/db 형태로 입력되어야 함
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": os.getenv("REDIS_URL"),
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#             "PASSWORD": os.getenv("REDIS_PASSWORD"),
#         }
#     }
# }

# Redis 연결 정보
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

REDIS_URL = os.getenv("REDIS_URL")


# AWS S3 설정 (개인)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = 'wouldulike-default-bucket-lunching'
AWS_S3_REGION_NAME = 'ap-northeast-2'

FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY")

# Firebase Cloud Messaging (HTTP v1)
FCM_PROJECT_ID = os.getenv("FCM_PROJECT_ID")
FCM_SERVICE_ACCOUNT_FILE = os.getenv("FCM_SERVICE_ACCOUNT_FILE")
FCM_SERVICE_ACCOUNT_JSON = os.getenv("FCM_SERVICE_ACCOUNT_JSON")


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


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),  # 30일
    'REFRESH_TOKEN_LIFETIME': timedelta(days=180),  # 180일 (로그인 유지 기간 연장)
    'ROTATE_REFRESH_TOKENS': False,  # 프론트 수정 없이 동일 refresh token 재사용
    'BLACKLIST_AFTER_ROTATION': False,  # rotation 비활성화와 함께 blacklist도 비활성화
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

KAKAO_ADMIN_KEY = os.getenv('KAKAO_ADMIN_KEY')

# Sign in with Apple (App Store Review Guideline 4.8)
APPLE_AUDIENCE = os.getenv('APPLE_AUDIENCE')  # 서비스 ID 또는 Bundle ID (예: com.example.app)
APPLE_TEAM_ID = os.getenv('APPLE_TEAM_ID')  # authorization_code 교환 시 사용 (선택)
APPLE_KEY_ID = os.getenv('APPLE_KEY_ID')  # authorization_code 교환 시 사용 (선택)
APPLE_PRIVATE_KEY = os.getenv('APPLE_PRIVATE_KEY')  # authorization_code 교환 시 사용 (선택)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}

# 내부 스케줄 트리거 보호용 토큰
# GCP Cloud Scheduler 등에서 X-CRON-TOKEN 헤더로 함께 전송해야 함.
CRON_SECRET_TOKEN = os.getenv("CRON_SECRET_TOKEN")

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

if DEBUG:
    STATIC_URL = '/static/'
    MEDIA_URL = ''
    MEDIA_ROOT = ''
else:
    AWS_S3_CUSTOM_DOMAIN = 'https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/'
    STATIC_URL = f"{AWS_S3_CUSTOM_DOMAIN}static/"
    MEDIA_URL = AWS_S3_CUSTOM_DOMAIN
    AWS_QUERYSTRING_AUTH = False  # S3에서 URL에 인증 정보 포함 안 함
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}


    # STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    # https://wouldulike-default-bucket.s3.ap-northeast-2.amazonaws.com/%EA%B0%80%EB%82%98+50%EC%A3%BC%EB%85%84+%EA%B8%B0%EB%85%90.jpg
