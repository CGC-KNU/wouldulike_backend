# APNs 인증 키 문제 해결 가이드

## 🔍 문제 상황

**BadEnvironmentKeyInToken 오류가 증가:**
- 업데이트 전: 2개
- 업데이트 후: 4개
- 오류 코드: `THIRD_PARTY_AUTH_ERROR` + `BadEnvironmentKeyInToken`

## 원인 분석

이 오류는 다음 상황에서 발생합니다:
1. **개발용 토큰**에 **프로덕션용 APNs 키**를 사용하거나
2. **프로덕션용 토큰**에 **개발용 APNs 키**를 사용하는 경우
3. Firebase Console에 **개발/프로덕션 키가 모두 업로드되지 않은 경우**

---

## ✅ 해결 방법

### 1단계: Firebase Console에서 현재 APNs 설정 확인

1. [Firebase Console](https://console.firebase.google.com/) 접속
2. 프로젝트 선택: `wouldulike-efe19`
3. 프로젝트 설정 (⚙️) → **클라우드 메시징** 탭
4. **APNs 인증 키** 또는 **APNs 인증서** 섹션 확인

**확인 사항:**
- [ ] 개발용(Sandbox) APNs 인증 키가 업로드되어 있는가?
- [ ] 프로덕션용(Production) APNs 인증 키가 업로드되어 있는가?
- [ ] 두 키가 모두 업로드되어 있는가?

---

### 2단계: Apple Developer Portal에서 APNs 인증 키 확인

#### 2.1 APNs 인증 키 확인

1. [Apple Developer Portal](https://developer.apple.com/account/) 접속
2. **Certificates, Identifiers & Profiles** → **Keys** 선택
3. APNs 관련 키 확인

**확인 사항:**
- [ ] APNs 인증 키가 생성되어 있는가?
- [ ] 키가 활성화되어 있는가?
- [ ] 키 파일(.p8)을 백업해두었는가?

#### 2.2 APNs 인증 키가 없다면 생성

1. Apple Developer Portal → Keys → **"+"** 클릭
2. **Key Name** 입력 (예: "APNs Auth Key for WouldULike")
3. **"Apple Push Notifications service (APNs)"** 체크 ✅
4. **Continue** → **Register**
5. **키 파일(.p8) 다운로드** ⚠️ **한 번만 다운로드 가능, 반드시 백업!**
6. **Key ID 기록** (나중에 필요)
7. **Team ID 확인** (Apple Developer Portal 상단)

---

### 3단계: Firebase Console에 APNs 인증 키 업로드

#### 3.1 개발용(Sandbox) APNs 인증 키 업로드

**중요:** APNs 인증 키는 개발/프로덕션을 구분하지 않습니다. 하나의 키로 두 환경 모두 사용 가능합니다.

하지만 Firebase Console에서는 다음을 확인해야 합니다:

1. Firebase Console → 프로젝트 설정 → 클라우드 메시징
2. **"APNs 인증 키"** 섹션
3. **"키 업로드"** 또는 **"편집"** 클릭
4. 다음 정보 입력:
   - **APNs 인증 키 파일(.p8)** 업로드
   - **Key ID** 입력
   - **Team ID** 입력
5. **"업로드"** 완료

#### 3.2 프로덕션용 APNs 인증서 업로드 (인증 키 대신 사용하는 경우)

만약 APNs 인증서(.p12)를 사용하는 경우:

1. **개발용 인증서** 확인:
   - Keychain Access에서 개발용 APNs 인증서 내보내기 (.p12)
   - Firebase Console에 업로드

2. **프로덕션용 인증서** 확인:
   - Keychain Access에서 프로덕션용 APNs 인증서 내보내기 (.p12)
   - Firebase Console에 업로드

---

### 4단계: Firebase Console 설정 확인

#### 4.1 APNs 인증 키 확인

Firebase Console → 프로젝트 설정 → 클라우드 메시징에서:

- [ ] APNs 인증 키가 업로드되어 있는가?
- [ ] Key ID가 올바른가?
- [ ] Team ID가 올바른가?

#### 4.2 APNs 인증서 확인 (인증 키 대신 사용하는 경우)

- [ ] 개발용 APNs 인증서가 업로드되어 있는가?
- [ ] 프로덕션용 APNs 인증서가 업로드되어 있는가?

---

### 5단계: iOS 앱 빌드 환경 확인

#### 5.1 개발 빌드 (Debug)

**개발 빌드에서 생성된 FCM 토큰:**
- 개발용 APNs 환경 사용
- Firebase Console에 개발용 APNs 키/인증서 필요

**확인 방법:**
- Xcode → Product → Scheme → Edit Scheme
- "Run" → Build Configuration이 "Debug"인지 확인

#### 5.2 프로덕션 빌드 (Release)

**프로덕션 빌드에서 생성된 FCM 토큰:**
- 프로덕션용 APNs 환경 사용
- Firebase Console에 프로덕션용 APNs 키/인증서 필요

**확인 방법:**
- Xcode → Product → Scheme → Edit Scheme
- "Archive" → Build Configuration이 "Release"인지 확인

---

### 6단계: 문제 해결 체크리스트

#### ✅ APNs 인증 키 방식 사용 시

- [ ] Apple Developer Portal에서 APNs 인증 키 생성 완료
- [ ] 키 파일(.p8) 다운로드 및 백업 완료
- [ ] Key ID 기록 완료
- [ ] Team ID 확인 완료
- [ ] Firebase Console에 APNs 인증 키 업로드 완료
- [ ] Key ID와 Team ID가 올바르게 입력되었는지 확인

#### ✅ APNs 인증서 방식 사용 시

- [ ] 개발용 APNs 인증서 생성 및 내보내기 완료
- [ ] 프로덕션용 APNs 인증서 생성 및 내보내기 완료
- [ ] Firebase Console에 개발용 인증서 업로드 완료
- [ ] Firebase Console에 프로덕션용 인증서 업로드 완료

---

## 🔧 단계별 해결 절차

### 방법 1: APNs 인증 키 사용 (권장)

**장점:** 하나의 키로 개발/프로덕션 모두 사용 가능

1. **Apple Developer Portal에서 키 확인/생성**
   ```
   Apple Developer Portal → Keys → APNs 관련 키 확인
   - 있으면: Key ID와 Team ID 확인
   - 없으면: 새로 생성
   ```

2. **Firebase Console에 업로드**
   ```
   Firebase Console → 프로젝트 설정 → 클라우드 메시징
   → APNs 인증 키 업로드
   → Key ID, Team ID 입력
   ```

3. **테스트**
   ```bash
   python manage.py test_notification
   ```

### 방법 2: APNs 인증서 사용

**주의:** 개발/프로덕션 인증서를 모두 업로드해야 함

1. **개발용 인증서 확인/생성**
   ```
   Keychain Access → 개발용 APNs 인증서 내보내기 (.p12)
   ```

2. **프로덕션용 인증서 확인/생성**
   ```
   Keychain Access → 프로덕션용 APNs 인증서 내보내기 (.p12)
   ```

3. **Firebase Console에 업로드**
   ```
   Firebase Console → 프로젝트 설정 → 클라우드 메시징
   → 개발용 인증서 업로드
   → 프로덕션용 인증서 업로드
   ```

4. **테스트**
   ```bash
   python manage.py test_notification
   ```

---

## 🧪 테스트 및 검증

### 1단계: 설정 확인

Firebase Console에서 다음을 확인:
- [ ] APNs 인증 키/인증서가 업로드되어 있는가?
- [ ] Key ID와 Team ID가 올바른가?

### 2단계: 토큰 테스트

```bash
# 드라이런 모드로 테스트
python manage.py test_notification
```

**확인 사항:**
- BadEnvironmentKeyInToken 오류가 감소했는가?
- 성공한 토큰 수가 증가했는가?

### 3단계: 실제 알림 전송 테스트

```bash
# 실제 알림 전송 (샘플 5개)
python manage.py test_notification --send --sample-size 5
```

---

## 📋 문제 해결 체크리스트

### 즉시 확인 사항

- [ ] Firebase Console → 프로젝트 설정 → 클라우드 메시징
- [ ] APNs 인증 키 또는 인증서가 업로드되어 있는지 확인
- [ ] 개발용과 프로덕션용이 모두 업로드되어 있는지 확인

### 해결 순서

1. **Firebase Console 확인**
   - APNs 인증 키/인증서 상태 확인
   - 누락된 키/인증서 식별

2. **Apple Developer Portal 확인**
   - APNs 인증 키 존재 여부 확인
   - 없으면 생성

3. **Firebase Console에 업로드**
   - 누락된 키/인증서 업로드
   - Key ID, Team ID 확인

4. **테스트 실행**
   - 드라이런 모드로 테스트
   - BadEnvironmentKeyInToken 오류 확인

---

## 🚨 주의사항

1. **APNs 인증 키 파일(.p8)은 한 번만 다운로드 가능**
   - 반드시 안전한 곳에 백업
   - 분실 시 새로 생성해야 함

2. **Key ID와 Team ID는 정확히 입력**
   - 오타가 있으면 인증 실패
   - Apple Developer Portal에서 정확히 확인

3. **개발/프로덕션 환경 구분**
   - 개발 빌드와 프로덕션 빌드는 다른 APNs 환경 사용
   - 두 환경 모두 지원하려면 적절한 키/인증서 필요

---

## 💡 추가 팁

### APNs 인증 키 vs 인증서

**APNs 인증 키 (권장):**
- 하나의 키로 개발/프로덕션 모두 사용 가능
- 관리가 간편함
- Apple에서 권장하는 방식

**APNs 인증서:**
- 개발용과 프로덕션용을 별도로 관리해야 함
- 더 복잡하지만 기존 시스템과 호환성 좋음

### 현재 프로젝트 확인 방법

Firebase Console에서 현재 어떤 방식을 사용하는지 확인:
- APNs 인증 키가 있으면 → 인증 키 방식 사용
- APNs 인증서가 있으면 → 인증서 방식 사용

---

**마지막 업데이트**: 2024년

