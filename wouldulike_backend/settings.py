from pathlib import Path
import os, json, environ
from django.core.exceptions import ImproperlyConfigured
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent


# .env 파일 로드
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


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


DEBUG = False


ALLOWED_HOSTS = ['*']
# ALLOWED_HOSTS = ['deliberate-lenette-coggiri-5ee7b85e.koyeb.app', 'localhost', '127.0.0.1']

# CORS_ALLOW_ALL_ORIGINS = True # 개발 중 모든 도메인 허용
# # 배포 시 특정 도메인만 허용
# # CORS_ALLOWED_ORIGINS = [
# #     "http://localhost:3000",
# #     "http://127.0.0.1:3000",
# # ]


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
    'rest_framework',
    'corsheaders',
    'storages',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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


DATABASE_ROUTERS = ['wouldulike_backend.db_routers.TypeDescriptionRouter']


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL"),  # 유저/비번 포함된 redis://username:password@host:port/0
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "USERNAME": "django-cache-user",  # 👈 여기 추가!
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

print("REDIS_URL:", os.getenv("REDIS_URL"))
print("REDIS_PASSWORD:", os.getenv("REDIS_PASSWORD"))


# AWS S3 설정 (개인)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = 'wouldulike-default-bucket'
AWS_S3_REGION_NAME = 'ap-northeast-2'


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

AUTH_USER_MODEL = 'auth.User'  # 기본 Django User 모델 사용

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

if DEBUG:
    # 개발 환경
    STATIC_URL = '/static/'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    MEDIA_URL = ''
    MEDIA_ROOT = ''
else:
    # 배포 환경
    AWS_S3_CUSTOM_DOMAIN = f'https://wouldulike-default-bucket.s3.ap-northeast-2.amazonaws.com/'
    STATIC_URL = f"https://wouldulike-default-bucket.s3.ap-northeast-2.amazonaws.com/static/"
    MEDIA_URL = f"https://wouldulike-default-bucket.s3.ap-northeast-2.amazonaws.com/"
    AWS_QUERYSTRING_AUTH = False  # S3에서 URL에 인증 정보 포함 안 함 (더 깔끔한 URL)
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',  # 정적 파일 캐싱 (24시간)
    }

    # STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    # DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    # https://wouldulike-default-bucket.s3.ap-northeast-2.amazonaws.com/%EA%B0%80%EB%82%98+50%EC%A3%BC%EB%85%84+%EA%B8%B0%EB%85%90.jpg