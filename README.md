# WouldULike Backend

WouldULike 백엔드 서버는 Django REST Framework 기반의 음식 추천 및 쿠폰 관리 플랫폼입니다.

## 📋 목차

- [기술 스택](#기술-스택)
- [주요 기능](#주요-기능)
- [프로젝트 구조](#프로젝트-구조)
- [설치 및 실행](#설치-및-실행)
- [환경 변수 설정](#환경-변수-설정)
- [API 엔드포인트](#api-엔드포인트)
- [데이터베이스](#데이터베이스)
- [관리 명령어](#관리-명령어)
- [배포](#배포)

## 🛠 기술 스택

- **Framework**: Django 4.2.6, Django REST Framework 3.15.2
- **인증**: JWT (djangorestframework-simplejwt)
- **데이터베이스**: PostgreSQL (다중 DB), SQLite (로컬 개발)
- **캐시**: Redis (django-redis)
- **스토리지**: AWS S3 (django-storages)
- **푸시 알림**: Firebase Cloud Messaging (FCM)
- **서버**: Gunicorn
- **Python**: 3.10.10

## ✨ 주요 기능

### 1. 사용자 인증 및 관리
- 카카오 로그인 연동
- JWT 기반 인증 (Access Token 30일, Refresh Token 90일)
- 게스트 사용자 지원
- 사용자 타입 코드 관리 (MBTI 기반)

### 2. 쿠폰 시스템
- 쿠폰 발급 및 사용 관리
- 쿠폰 타입별 혜택 설정 (고정 금액/퍼센트 할인)
- 레스토랑별 쿠폰 혜택 커스터마이징
- 쿠폰 만료 자동 관리
- 쿠폰 상태 추적 (발급/사용/만료/취소)

### 3. 스탬프 시스템
- 레스토랑별 스탬프 적립
- 스탬프 기반 쿠폰 발급
- 스탬프 이벤트 히스토리 관리

### 4. 추천인 시스템
- 초대 코드 생성 및 관리
- 추천인 보상 지급
- 추천인 자격 검증

### 5. 레스토랑 정보
- 레스토랑 검색 및 조회
- 제휴 레스토랑 관리
- 캠퍼스 레스토랑 정보
- 레스토랑 즐겨찾기

### 6. 트렌드 정보
- 음식 트렌드 게시물 관리
- 이미지 업로드 및 관리

### 7. 푸시 알림
- FCM 기반 푸시 알림 발송
- 스케줄링된 알림 관리
- 사용자별 FCM 토큰 관리

## 📁 프로젝트 구조

```
wouldulike_backend/
├── accounts/              # 사용자 인증 및 계정 관리
│   ├── models.py         # User 모델
│   ├── views.py          # 인증 뷰 (카카오 로그인, JWT)
│   └── urls.py           # 인증 API 엔드포인트
├── coupons/              # 쿠폰 시스템
│   ├── models.py         # Coupon, Campaign, StampWallet 등
│   ├── api/              # 쿠폰 API
│   ├── service.py        # 쿠폰 비즈니스 로직
│   └── tasks.py          # 쿠폰 만료 처리 등
├── restaurants/          # 레스토랑 정보
│   └── models.py         # Restaurant, AffiliateRestaurant
├── notifications/        # 푸시 알림
│   ├── models.py         # Notification 모델
│   └── utils.py          # FCM 발송 유틸리티
├── trends/              # 트렌드 정보
├── guests/              # 게스트 사용자
├── campus_restaurants/  # 캠퍼스 레스토랑
├── food_by_type/        # 음식 타입별 정보
├── type_description/    # 타입 설명
├── wouldulike_backend/  # 프로젝트 설정
│   ├── settings.py       # Django 설정
│   ├── urls.py          # URL 라우팅
│   └── db_routers.py    # 데이터베이스 라우터
├── requirements.txt     # Python 패키지 의존성
├── Procfile            # 배포 설정
└── runtime.txt         # Python 버전
```

## 🚀 설치 및 실행

### 1. 저장소 클론

```bash
git clone <repository-url>
cd wouldulike_backend
```

### 2. 가상 환경 생성 및 활성화

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env` 파일을 생성하고 필요한 환경 변수를 설정합니다. (자세한 내용은 [환경 변수 설정](#환경-변수-설정) 참조)

`secrets.json` 파일을 생성하고 필요한 시크릿 정보를 설정합니다.

### 5. 데이터베이스 마이그레이션

```bash
python manage.py migrate
```

### 6. 서버 실행

```bash
# 개발 서버
python manage.py runserver

# 프로덕션 (Gunicorn)
gunicorn wouldulike_backend.wsgi:application --bind 0.0.0.0:8000
```

## ⚙️ 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 환경 변수를 설정하세요:

### 데이터베이스
```env
# 기본 데이터베이스 (사용자 데이터)
default_db_name=your_db_name
default_db_user=your_db_user
default_db_password=your_db_password
default_db_host=your_db_host
default_db_port=5432

# RDS 데이터베이스 (유형 데이터)
rds_db_name=your_rds_db_name
rds_db_user=your_rds_db_user
rds_db_password=your_rds_password
rds_db_host=your_rds_host
rds_db_port=5432

# CloudSQL 데이터베이스
cloudsql_db_name=your_cloudsql_db_name
cloudsql_db_user=your_cloudsql_db_user
cloudsql_db_password=your_cloudsql_password
cloudsql_db_host=your_cloudsql_host
cloudsql_db_port=5432

# 로컬 SQLite 사용 (개발용)
DJANGO_USE_LOCAL_SQLITE=0
DJANGO_DISABLE_EXTERNAL_DBS=0
```

### Redis
```env
REDIS_URL=redis://username:password@host:port/db
REDIS_HOST=your_redis_host
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
```

### AWS S3
```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Firebase Cloud Messaging
```env
FCM_SERVER_KEY=your_fcm_server_key
FCM_PROJECT_ID=your_fcm_project_id
FCM_SERVICE_ACCOUNT_FILE=path/to/service_account.json
FCM_SERVICE_ACCOUNT_JSON=your_service_account_json
```

### 기타
```env
SECRET_KEY=your_django_secret_key
DEBUG=True
KAKAO_ADMIN_KEY=your_kakao_admin_key

# 운영 관리자 계정 설정
OPERATIONS_ADMIN_ACCOUNTS=ROLE:KAKAO_ID:PASSWORD;ROLE2:KAKAO_ID2:PASSWORD2
OPERATIONS_ADMIN_DEFAULT_PASSWORD=default_password
OPERATIONS_ADMIN_RESET_PASSWORDS=0
```

## 📡 API 엔드포인트

### 인증 (`/api/auth/`)
- `POST /api/auth/kakao` - 카카오 로그인
- `POST /api/auth/refresh` - 토큰 갱신
- `POST /api/auth/verify` - 토큰 검증
- `POST /api/auth/logout` - 로그아웃
- `POST /api/auth/unlink` - 계정 연동 해제
- `POST /auth/dev-login` - 개발용 로그인 (로컬 전용)

### 쿠폰 (`/api/`)
- `GET /api/coupons/my/` - 내 쿠폰 목록 조회
- `POST /api/coupons/signup/complete/` - 회원가입 완료 쿠폰 발급
- `POST /api/coupons/redeem/` - 쿠폰 사용
- `POST /api/coupons/check/` - 쿠폰 확인
- `GET /api/coupons/invite/my/` - 내 초대 코드 조회
- `POST /api/coupons/referrals/accept/` - 추천인 코드 입력
- `POST /api/coupons/referrals/qualify/` - 추천인 자격 검증
- `POST /api/coupons/flash/claim/` - 플래시 쿠폰 발급

### 스탬프 (`/api/`)
- `POST /api/coupons/stamps/add/` - 스탬프 적립
- `GET /api/coupons/stamps/my/` - 내 스탬프 현황 조회
- `GET /api/coupons/stamps/my/all/` - 모든 레스토랑 스탬프 현황 조회

### 게스트 (`/guests/`)
- `POST /guests/update/fcm_token/` - 게스트 FCM 토큰 업데이트

### 레스토랑 (`/restaurants/`)
- 레스토랑 검색 및 조회 API

### 트렌드 (`/trends/`)
- 트렌드 정보 조회 API

### 알림 (`/notifications/`)
- 알림 조회 및 관리 API

## 🗄 데이터베이스

### 데이터베이스 구조
- **default**: 사용자 데이터, 쿠폰, 스탬프 등
- **rds**: 유형 데이터
- **cloudsql**: 레스토랑 정보 (읽기 전용)

### 데이터베이스 라우터
- `TypeDescriptionRouter`: 타입 설명 관련 모델을 RDS로 라우팅

### 로컬 개발
로컬 개발 시 SQLite를 사용할 수 있습니다:
```env
DJANGO_USE_LOCAL_SQLITE=1
```

## 🔧 관리 명령어

### 관리자 포털 설정
```bash
python manage.py setup_admin_portal
```
운영 관리자 계정을 설정합니다. `OPERATIONS_ADMIN_ACCOUNTS` 환경 변수로 계정을 구성할 수 있습니다.

### 테스트 초대 코드 생성
```bash
python manage.py create_test_invite_code \
  --kakao-id 910000001 \
  --type-code ISTJ
```

### 쿠폰 만료 처리
```bash
python manage.py expire_coupons
```

### 스케줄링된 알림 발송
```bash
python manage.py send_scheduled_notifications
```

### 사용자 데이터 삭제
```bash
python manage.py delete_user_data --kakao-id <kakao_id>
```

### 쿠폰 시드 데이터 초기화
```bash
python manage.py init_coupon_seed
python manage.py seed_dev_coupons
```

## 🚢 배포

### Heroku/Koyeb 배포

`Procfile`에 정의된 명령어로 배포됩니다:

```procfile
release: python manage.py migrate && python manage.py setup_admin_portal
web: gunicorn wouldulike_backend.wsgi:application --bind 0.0.0.0:$PORT --workers=2
```

### Google Cloud Build

`cloudbuild.yaml` 파일을 사용하여 Google Cloud Build로 배포할 수 있습니다.

### 환경 변수 설정
배포 환경에서 위의 모든 환경 변수를 설정해야 합니다.

## 📝 추가 문서

프로젝트에는 다음 가이드 문서들이 포함되어 있습니다:
- `APNs_인증_키_문제_해결_가이드.md` - APNs 인증 키 문제 해결
- `iOS_푸시_알림_구현_가이드.md` - iOS 푸시 알림 구현 가이드
- `iOS_푸시_알림_문제_진단_및_해결.md` - 푸시 알림 문제 진단
- `푸시_알림_테스트_가이드.md` - 푸시 알림 테스트 가이드
- `프론트엔드_토큰_자동갱신_구현_가이드.md` - 토큰 자동 갱신 가이드

## 📄 라이선스

이 프로젝트는 비공개 프로젝트입니다.

## 👥 기여

프로젝트 기여에 대한 문의는 프로젝트 관리자에게 연락하세요.
