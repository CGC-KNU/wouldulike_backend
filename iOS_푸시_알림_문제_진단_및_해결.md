# iOS 푸시 알림 문제 진단 및 해결 가이드

## 🔍 현재 상황 분석

테스트 결과:
- ✅ 성공: 18개 (아마도 Android 또는 올바르게 설정된 iOS)
- ❌ 실패: 30개 (대부분 iOS)
- 주요 오류: `SENDER_ID_MISMATCH` (403), `BadEnvironmentKeyInToken` (401)

---

## ❌ 문제 1: SENDER_ID_MISMATCH (403)

### 증상
```
FCM send failed: {'error': {'code': 403, 'message': 'SenderId mismatch', 
'status': 'PERMISSION_DENIED', 'details': [{'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 
'errorCode': 'SENDER_ID_MISMATCH'}]}}
```

### 원인
iOS 앱의 `GoogleService-Info.plist`에 있는 **Sender ID (GCM_SENDER_ID)**와 백엔드에서 사용하는 Firebase 프로젝트의 Sender ID가 일치하지 않습니다.

### 해결 방법

#### 1단계: 백엔드에서 사용하는 Firebase 프로젝트 확인

**현재 백엔드 프로젝트 ID:** `wouldulike-efe19`

환경 변수 확인:
```bash
echo $FCM_PROJECT_ID
# 또는
python manage.py shell
>>> from django.conf import settings
>>> print(settings.FCM_PROJECT_ID)
```

#### 2단계: iOS 앱의 GoogleService-Info.plist 확인

**iOS 프로젝트에서 확인:**
1. Xcode에서 `GoogleService-Info.plist` 파일 열기
2. 다음 키 확인:
   - `PROJECT_ID`: Firebase 프로젝트 ID
   - `GCM_SENDER_ID`: Sender ID (이 값이 중요!)

**또는 터미널에서 확인:**
```bash
# iOS 프로젝트 디렉토리로 이동
cd /path/to/ios/project

# GoogleService-Info.plist 내용 확인
plutil -p GoogleService-Info.plist | grep -E "PROJECT_ID|GCM_SENDER_ID"
```

#### 3단계: Firebase Console에서 확인

1. [Firebase Console](https://console.firebase.google.com/) 접속
2. 프로젝트 선택 (`wouldulike-efe19`)
3. 프로젝트 설정 (⚙️) → "내 앱" 섹션
4. iOS 앱 선택
5. **Sender ID 확인** (일반적으로 프로젝트 번호와 동일)

#### 4단계: 일치 여부 확인

**확인해야 할 값:**
- 백엔드: `FCM_PROJECT_ID` = `wouldulike-efe19`
- iOS 앱: `GoogleService-Info.plist`의 `PROJECT_ID` = `wouldulike-efe19`
- iOS 앱: `GoogleService-Info.plist`의 `GCM_SENDER_ID` = 백엔드 프로젝트의 Sender ID와 일치해야 함

**일치하지 않는 경우 해결 방법:**

**방법 A: iOS 앱의 GoogleService-Info.plist 교체 (권장)**

1. Firebase Console → 프로젝트 설정 → iOS 앱
2. 올바른 프로젝트(`wouldulike-efe19`)의 `GoogleService-Info.plist` 다운로드
3. iOS 프로젝트의 기존 파일 교체
4. Xcode에서 파일이 올바르게 포함되었는지 확인
5. 앱 재빌드 및 재배포

**방법 B: 백엔드가 다른 프로젝트를 사용해야 하는 경우**

1. iOS 앱이 사용하는 Firebase 프로젝트 확인
2. 백엔드 환경 변수 `FCM_PROJECT_ID`를 해당 프로젝트로 변경
3. 해당 프로젝트의 서비스 계정 키 사용

---

## ❌ 문제 2: BadEnvironmentKeyInToken (401)

### 증상
```
FCM send failed: {'error': {'code': 401, 'message': 'Auth error from APNS or Web Push Service', 
'status': 'UNAUTHENTICATED', 'details': [
  {'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 'errorCode': 'THIRD_PARTY_AUTH_ERROR'}, 
  {'@type': 'type.googleapis.com/google.firebase.fcm.v1.ApnsError', 'statusCode': 403, 'reason': 'BadEnvironmentKeyInToken'}
]}}
```

### 원인
APNs 인증 키가 잘못된 환경(개발/프로덕션)으로 설정되었거나, 토큰이 개발용인데 프로덕션 키를 사용하거나 그 반대인 경우입니다.

### 해결 방법

#### 1단계: Firebase Console에서 APNs 설정 확인

1. Firebase Console → 프로젝트 설정 → 클라우드 메시징 탭
2. "APNs 인증 키" 또는 "APNs 인증서" 섹션 확인
3. **개발용과 프로덕션용이 모두 업로드되어 있는지 확인**

#### 2단계: 앱 빌드 환경 확인

**개발 빌드 (Debug):**
- 개발용 APNs 인증 키/인증서 필요
- 개발용 FCM 토큰 생성

**프로덕션 빌드 (Release/App Store):**
- 프로덕션용 APNs 인증 키/인증서 필요
- 프로덕션용 FCM 토큰 생성

#### 3단계: APNs 인증 키 재업로드

**개발용과 프로덕션용 모두 업로드:**

1. Apple Developer Portal → Keys
2. APNs 인증 키 확인 (또는 새로 생성)
3. Firebase Console → 프로젝트 설정 → 클라우드 메시징
4. **개발용 APNs 인증 키 업로드** (Sandbox)
5. **프로덕션용 APNs 인증 키 업로드** (Production)

**또는 APNs 인증서 사용 시:**
- 개발용 인증서: `.p12` 파일 업로드
- 프로덕션용 인증서: `.p12` 파일 업로드

#### 4단계: 앱 재빌드 및 토큰 재생성

1. 앱을 완전히 삭제하고 재설치
2. 새로운 FCM 토큰 생성
3. 백엔드로 새 토큰 전송
4. 테스트 재실행

---

## 🔧 종합 해결 체크리스트

### ✅ Firebase 프로젝트 일치 확인

- [ ] 백엔드 `FCM_PROJECT_ID` = `wouldulike-efe19`
- [ ] iOS 앱 `GoogleService-Info.plist`의 `PROJECT_ID` = `wouldulike-efe19`
- [ ] iOS 앱 `GoogleService-Info.plist`의 `GCM_SENDER_ID` = 백엔드 프로젝트의 Sender ID와 일치
- [ ] iOS 앱 `GoogleService-Info.plist`의 `BUNDLE_ID` = `com.coggiri.wouldulike0117`

### ✅ APNs 인증 설정 확인

- [ ] Firebase Console에 개발용 APNs 인증 키/인증서 업로드됨
- [ ] Firebase Console에 프로덕션용 APNs 인증 키/인증서 업로드됨
- [ ] Apple Developer Portal에서 APNs 인증 키가 올바르게 생성됨

### ✅ iOS 앱 설정 확인

- [ ] `GoogleService-Info.plist`가 프로젝트에 포함됨
- [ ] `GoogleService-Info.plist`의 Target Membership에 앱 타겟이 체크됨
- [ ] Release 빌드에도 `GoogleService-Info.plist`가 포함됨
- [ ] Firebase 초기화 코드(`FirebaseApp.configure()`)가 실행됨

### ✅ 백엔드 설정 확인

- [ ] `FCM_PROJECT_ID` 환경 변수 설정됨
- [ ] `FCM_SERVICE_ACCOUNT_FILE` 또는 `FCM_SERVICE_ACCOUNT_JSON` 설정됨
- [ ] 서비스 계정 키가 올바른 프로젝트(`wouldulike-efe19`)의 것임

---

## 🧪 테스트 방법

### 1단계: 설정 확인 테스트

```bash
python manage.py test_notification
```

드라이런 모드로 설정만 검증합니다.

### 2단계: 특정 토큰으로 테스트

실패한 토큰 중 하나로 테스트:
```bash
python manage.py test_notification --token "실패한-토큰-여기" --send
```

### 3단계: iOS 앱에서 새 토큰 생성

1. 앱 완전 삭제
2. 앱 재설치
3. 앱 실행 후 FCM 토큰 확인
4. 새 토큰으로 테스트

---

## 📋 단계별 해결 절차

### 즉시 확인 사항

1. **iOS 앱의 GoogleService-Info.plist 확인**
   ```bash
   # iOS 프로젝트에서
   plutil -p GoogleService-Info.plist
   ```
   - `PROJECT_ID`가 `wouldulike-efe19`인지 확인
   - `GCM_SENDER_ID` 값 확인

2. **Firebase Console 확인**
   - 프로젝트 `wouldulike-efe19` 선택
   - 프로젝트 설정 → iOS 앱
   - Sender ID 확인
   - 클라우드 메시징 → APNs 인증 키/인증서 확인

3. **백엔드 환경 변수 확인**
   ```bash
   echo $FCM_PROJECT_ID
   # should be: wouldulike-efe19
   ```

### 해결 순서

1. **GoogleService-Info.plist 교체**
   - Firebase Console에서 올바른 프로젝트의 파일 다운로드
   - iOS 프로젝트에 교체
   - 앱 재빌드

2. **APNs 인증 키 재업로드**
   - 개발용과 프로덕션용 모두 업로드
   - Firebase Console에서 확인

3. **앱 재배포**
   - 새 토큰 생성
   - 테스트 재실행

---

## 🚨 주의사항

1. **GoogleService-Info.plist는 프로젝트별로 다릅니다**
   - 다른 Firebase 프로젝트의 파일을 사용하면 안 됩니다
   - 반드시 `wouldulike-efe19` 프로젝트의 파일을 사용해야 합니다

2. **APNs 인증 키는 환경별로 다릅니다**
   - 개발 빌드와 프로덕션 빌드는 다른 키를 사용할 수 있습니다
   - 두 환경 모두 Firebase에 업로드되어 있어야 합니다

3. **토큰은 앱 재설치 시 변경됩니다**
   - 문제 해결 후 앱을 재설치하여 새 토큰을 생성하는 것이 좋습니다

---

## 📞 추가 확인 필요 사항

다음 정보를 확인하면 더 정확한 진단이 가능합니다:

1. **iOS 앱의 GoogleService-Info.plist 내용**
   - `PROJECT_ID`
   - `GCM_SENDER_ID`
   - `BUNDLE_ID`

2. **Firebase Console의 Sender ID**
   - 프로젝트 설정에서 확인

3. **앱 빌드 환경**
   - Debug 빌드인지 Release 빌드인지
   - TestFlight인지 App Store인지

이 정보를 확인하면 더 구체적인 해결 방법을 제시할 수 있습니다.

---

**마지막 업데이트**: 2024년

