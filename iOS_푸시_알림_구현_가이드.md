# iOS 푸시 알림 구현 가이드

## 📋 개요

iOS 앱에서 푸시 알림을 구현하기 위해 필요한 모든 조건과 설정 사항을 정리한 문서입니다. Firebase Cloud Messaging (FCM)을 사용하는 경우를 기준으로 작성되었습니다.

---

## ✅ 필수 조건 체크리스트

### 1. Apple Developer 계정 및 인증서 설정

#### 1.1 Apple Developer 계정
- [ ] **Apple Developer Program 가입** (연간 $99)
  - [Apple Developer Program](https://developer.apple.com/programs/) 가입 필요
  - 개인 또는 조직 계정 모두 가능
  - 가입 후 승인까지 24-48시간 소요 가능

#### 1.2 App ID 등록 및 Push Notifications Capability 활성화
- [ ] **Apple Developer Portal에서 App ID 생성**
  1. [Apple Developer Portal](https://developer.apple.com/account/) 접속
  2. Certificates, Identifiers & Profiles → Identifiers 선택
  3. "+" 버튼 클릭하여 새 App ID 생성
  4. App ID Prefix 선택 (Team ID)
  5. Description 입력 (예: "WouldULike iOS App")
  6. **Bundle ID 입력** (예: `com.coggiri.wouldulike0117`)
  7. **Capabilities에서 "Push Notifications" 체크** ✅
  8. Continue → Register 완료

#### 1.3 APNs 인증서 또는 키 생성

**방법 1: APNs 인증서 생성 (기존 방식)**
- [ ] **APNs 인증서 생성**
  1. Apple Developer Portal → Certificates → "+" 클릭
  2. "Apple Push Notification service SSL (Sandbox & Production)" 선택
  3. App ID 선택
  4. CSR 파일 생성:
     - Keychain Access → Certificate Assistant → Request a Certificate from a Certificate Authority
     - User Email Address 입력
     - Common Name 입력
     - "Save to disk" 선택
  5. CSR 파일 업로드
  6. 인증서 다운로드 및 설치 (더블클릭하여 Keychain에 추가)

**방법 2: APNs 인증 키 생성 (권장, 더 간편)**
- [ ] **APNs 인증 키 생성**
  1. Apple Developer Portal → Keys → "+" 클릭
  2. Key Name 입력 (예: "APNs Auth Key")
  3. **"Apple Push Notifications service (APNs)" 체크** ✅
  4. Continue → Register
  5. **키 파일(.p8) 다운로드** (한 번만 다운로드 가능, 백업 필수!)
  6. **Key ID 기록** (나중에 필요)
  7. **Team ID 확인** (Apple Developer Portal 상단에서 확인)

---

### 2. Firebase 프로젝트 설정

#### 2.1 Firebase 프로젝트 생성 및 iOS 앱 추가
- [ ] **Firebase Console에서 프로젝트 생성**
  1. [Firebase Console](https://console.firebase.google.com/) 접속
  2. 프로젝트 추가 또는 기존 프로젝트 선택
  3. 프로젝트 설정 → "내 앱" 섹션
  4. iOS 앱 추가 버튼 클릭
  5. **Bundle ID 입력** (Apple Developer에서 등록한 것과 동일해야 함)
  6. App nickname 입력 (선택사항)
  7. App Store ID 입력 (선택사항)
  8. "앱 등록" 완료

#### 2.2 GoogleService-Info.plist 다운로드
- [ ] **GoogleService-Info.plist 파일 다운로드**
  1. Firebase Console → 프로젝트 설정 → iOS 앱
  2. "GoogleService-Info.plist" 다운로드 버튼 클릭
  3. 파일을 iOS 프로젝트 루트 디렉토리에 추가
  4. Xcode에서 파일을 프로젝트에 드래그 앤 드롭
  5. **"Copy items if needed" 체크** ✅
  6. **앱 타겟에 포함 확인** (Target Membership)

#### 2.3 Firebase에서 APNs 인증 키 업로드
- [ ] **APNs 인증 키를 Firebase에 업로드**
  1. Firebase Console → 프로젝트 설정 → 클라우드 메시징 탭
  2. "APNs 인증 키" 섹션
  3. "키 업로드" 클릭
  4. **APNs 인증 키(.p8) 파일 업로드**
  5. **Key ID 입력** (Apple Developer Portal에서 확인한 값)
  6. **Team ID 입력** (Apple Developer Portal에서 확인한 값)
  7. "업로드" 완료

**또는 APNs 인증서 업로드 (인증 키 대신)**
- [ ] **APNs 인증서를 Firebase에 업로드**
  1. Keychain Access에서 인증서 내보내기 (.p12 형식)
  2. Firebase Console → 프로젝트 설정 → 클라우드 메시징 탭
  3. "APNs 인증서" 섹션
  4. 인증서 파일(.p12) 업로드
  5. 인증서 비밀번호 입력 (내보낼 때 설정한 비밀번호)

#### 2.4 Firebase Cloud Messaging 서비스 계정 설정
- [ ] **서비스 계정 키 생성**
  1. Firebase Console → 프로젝트 설정 → 서비스 계정 탭
  2. "새 비공개 키 만들기" 클릭
  3. JSON 파일 다운로드 (백엔드에서 사용)
  4. **백엔드 환경 변수 설정:**
     - `FCM_PROJECT_ID`: Firebase 프로젝트 ID
     - `FCM_SERVICE_ACCOUNT_FILE`: 서비스 계정 JSON 파일 경로
     - 또는 `FCM_SERVICE_ACCOUNT_JSON`: 서비스 계정 JSON 문자열

---

### 3. Xcode 프로젝트 설정

#### 3.1 Firebase SDK 설치

**방법 1: CocoaPods 사용 (권장)**
- [ ] **CocoaPods 설치 확인**
  ```bash
  pod --version
  ```
  - 설치되어 있지 않다면:
    ```bash
    sudo gem install cocoapods
    ```

- [ ] **Podfile 생성 및 설정**
  1. iOS 프로젝트 루트 디렉토리로 이동
  2. Podfile 생성:
     ```bash
     pod init
     ```
  3. Podfile 편집:
     ```ruby
     platform :ios, '13.0'  # 최소 iOS 버전
     
     target 'YourAppName' do
       use_frameworks!
       
       # Firebase SDK
       pod 'Firebase/Messaging'  # 푸시 알림
       pod 'Firebase/Analytics'  # Analytics (선택사항)
     end
     ```
  4. Firebase SDK 설치:
     ```bash
     pod install
     ```
  5. **`.xcworkspace` 파일로 프로젝트 열기** (`.xcodeproj` 아님!)

**방법 2: Swift Package Manager 사용**
- [ ] **Swift Package Manager로 Firebase 추가**
  1. Xcode → File → Add Packages...
  2. URL 입력: `https://github.com/firebase/firebase-ios-sdk`
  3. Version: "Up to Next Major Version" 선택
  4. Add Package
  5. 다음 제품 선택:
     - FirebaseMessaging
     - FirebaseAnalytics (선택사항)

#### 3.2 Capabilities 설정
- [ ] **Push Notifications Capability 활성화**
  1. Xcode에서 프로젝트 선택
  2. TARGETS → 앱 타겟 선택
  3. "Signing & Capabilities" 탭
  4. "+ Capability" 클릭
  5. **"Push Notifications" 추가** ✅
  6. **"Background Modes" 추가** (선택사항, 백그라운드 알림 수신 시)
     - "Remote notifications" 체크

#### 3.3 Bundle Identifier 확인
- [ ] **Bundle ID가 Apple Developer와 일치하는지 확인**
  1. Xcode → 프로젝트 → TARGETS → 앱 타겟
  2. "General" 탭 → "Bundle Identifier" 확인
  3. **Apple Developer Portal에 등록한 Bundle ID와 정확히 일치해야 함**
  4. 예: `com.coggiri.wouldulike0117`

#### 3.4 Signing & Capabilities 설정
- [ ] **자동 서명 활성화**
  1. "Signing & Capabilities" 탭
  2. "Automatically manage signing" 체크 ✅
  3. Team 선택 (Apple Developer 계정)
  4. Provisioning Profile이 자동으로 생성/업데이트됨

- [ ] **수동 서명 사용 시**
  1. "Automatically manage signing" 체크 해제
  2. Provisioning Profile 수동 선택
  3. **Push Notifications이 포함된 Provisioning Profile 사용**

#### 3.5 Info.plist 설정
- [ ] **필요한 권한 설정 확인**
  - `UIBackgroundModes` (백그라운드 알림 수신 시)
  - `FirebaseAppDelegateProxyEnabled` (Firebase 사용 시, 기본값: true)

---

### 4. 앱 코드 구현

#### 4.1 Firebase 초기화
- [ ] **Firebase 초기화 코드 추가**

**SwiftUI 사용 시 (App.swift):**
```swift
import SwiftUI
import Firebase
import FirebaseMessaging

@main
struct YourApp: App {
    init() {
        FirebaseApp.configure()
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
```

**UIKit 사용 시 (AppDelegate.swift):**
```swift
import UIKit
import Firebase
import FirebaseMessaging

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {
    
    func application(_ application: UIApplication, 
                    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        FirebaseApp.configure()
        return true
    }
    
    // ... 나머지 코드
}
```

#### 4.2 푸시 알림 권한 요청
- [ ] **앱 시작 시 푸시 알림 권한 요청**
```swift
import UserNotifications
import FirebaseMessaging

// AppDelegate 또는 ViewController에서
func requestNotificationPermission() {
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
        if granted {
            print("✅ 푸시 알림 권한 허용됨")
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        } else {
            print("❌ 푸시 알림 권한 거부됨")
        }
    }
}
```

#### 4.3 APNs 토큰 등록
- [ ] **APNs 토큰 등록 핸들러 구현**
```swift
// AppDelegate에서
func application(_ application: UIApplication, 
                didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
    print("✅ APNs 토큰 등록 성공")
    
    // Firebase에 토큰 전달
    Messaging.messaging().apnsToken = deviceToken
    
    // FCM 토큰 가져오기
    Messaging.messaging().token { token, error in
        if let error = error {
            print("❌ FCM 토큰 가져오기 실패: \(error)")
        } else if let token = token {
            print("✅ FCM 토큰: \(token)")
            // 백엔드로 토큰 전송
            self.sendTokenToBackend(token)
        }
    }
}

func application(_ application: UIApplication, 
                didFailToRegisterForRemoteNotificationsWithError error: Error) {
    print("❌ APNs 토큰 등록 실패: \(error)")
}
```

#### 4.4 FCM 토큰 수신 및 백엔드 전송
- [ ] **FCM 토큰 수신 및 백엔드 API 호출**
```swift
// FCM 토큰 새로고침 감지
Messaging.messaging().delegate = self

extension AppDelegate: MessagingDelegate {
    func messaging(_ messaging: Messaging, didReceiveRegistrationToken fcmToken: String?) {
        print("✅ FCM 토큰 새로고침: \(fcmToken ?? "nil")")
        
        guard let token = fcmToken else { return }
        
        // 백엔드로 토큰 전송
        sendTokenToBackend(token)
    }
}

func sendTokenToBackend(_ token: String) {
    // 백엔드 API 호출
    guard let url = URL(string: "https://your-backend.com/api/fcm-token") else { return }
    
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("Bearer YOUR_AUTH_TOKEN", forHTTPHeaderField: "Authorization")
    
    let body: [String: Any] = ["fcm_token": token]
    request.httpBody = try? JSONSerialization.data(withJSONObject: body)
    
    URLSession.shared.dataTask(with: request) { data, response, error in
        if let error = error {
            print("❌ 토큰 전송 실패: \(error)")
        } else {
            print("✅ 토큰 전송 성공")
        }
    }.resume()
}
```

#### 4.5 푸시 알림 수신 처리
- [ ] **포그라운드에서 알림 수신 처리**
```swift
// AppDelegate에서
extension AppDelegate: UNUserNotificationCenterDelegate {
    // 포그라운드에서 알림 수신 시
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        let userInfo = notification.request.content.userInfo
        print("📬 포그라운드 알림 수신: \(userInfo)")
        
        // 알림 표시 옵션 설정
        if #available(iOS 14.0, *) {
            completionHandler([.banner, .sound, .badge])
        } else {
            completionHandler([.alert, .sound, .badge])
        }
    }
    
    // 알림 탭 시 처리
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let userInfo = response.notification.request.content.userInfo
        print("👆 알림 탭됨: \(userInfo)")
        
        // 알림 데이터에 따라 화면 이동 등 처리
        handleNotificationTap(userInfo)
        
        completionHandler()
    }
}

// UNUserNotificationCenterDelegate 설정
func application(_ application: UIApplication, 
                didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    FirebaseApp.configure()
    
    // 알림 센터 델리게이트 설정
    UNUserNotificationCenter.current().delegate = self
    
    // FCM 메시징 델리게이트 설정
    Messaging.messaging().delegate = self
    
    return true
}
```

#### 4.6 백그라운드에서 알림 수신 처리
- [ ] **백그라운드 알림 수신 처리**
```swift
// AppDelegate에서
func application(_ application: UIApplication,
                didReceiveRemoteNotification userInfo: [AnyHashable: Any],
                fetchCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void) {
    print("📬 백그라운드 알림 수신: \(userInfo)")
    
    // 데이터 처리
    handleBackgroundNotification(userInfo)
    
    completionHandler(.newData)
}
```

---

### 5. 백엔드 설정

#### 5.1 환경 변수 설정
- [ ] **필수 환경 변수 설정**
```bash
# Firebase 프로젝트 ID
FCM_PROJECT_ID=your-firebase-project-id

# 서비스 계정 키 파일 경로 또는 JSON 문자열
FCM_SERVICE_ACCOUNT_FILE=/path/to/service-account-key.json
# 또는
FCM_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

#### 5.2 FCM 서버 키 확인 (HTTP v1 API 사용 시)
- [ ] **서비스 계정 키가 올바르게 설정되었는지 확인**
  - Firebase Console → 프로젝트 설정 → 서비스 계정
  - "새 비공개 키 만들기"로 생성한 JSON 파일 사용
  - 파일이 올바른 경로에 있는지 확인
  - 파일 권한 확인 (읽기 가능)

#### 5.3 푸시 알림 전송 API 구현 확인
- [ ] **백엔드에서 FCM 토큰으로 푸시 알림 전송 가능한지 확인**
  - FCM HTTP v1 API 사용
  - 서비스 계정 인증 정상 작동 확인
  - 테스트 알림 전송 성공 확인

---

### 6. 테스트 및 검증

#### 6.1 개발 환경 테스트
- [ ] **실제 기기에서 테스트** (시뮬레이터는 푸시 알림 미지원)
  1. 실제 iOS 기기 연결
  2. Xcode에서 기기 선택
  3. 앱 빌드 및 실행
  4. 푸시 알림 권한 요청 확인
  5. FCM 토큰 수신 확인
  6. 백엔드로 토큰 전송 확인

#### 6.2 Firebase Console에서 테스트
- [ ] **Firebase Console에서 테스트 알림 전송**
  1. Firebase Console → 클라우드 메시징
  2. "새 알림" 클릭
  3. 알림 제목 및 본문 입력
  4. "테스트 메시지 전송" 클릭
  5. FCM 토큰 입력
  6. "테스트" 클릭
  7. 앱에서 알림 수신 확인

#### 6.3 백엔드에서 테스트
- [ ] **백엔드 API를 통한 테스트 알림 전송**
  - 저장된 FCM 토큰으로 테스트 알림 전송
  - 성공/실패 응답 확인
  - 앱에서 알림 수신 확인

#### 6.4 프로덕션 환경 테스트
- [ ] **TestFlight 또는 App Store 배포 후 테스트**
  1. Release 빌드로 Archive 생성
  2. TestFlight에 업로드
  3. 실제 기기에서 TestFlight 앱 설치
  4. 푸시 알림 수신 확인
  5. **중요: Release 빌드에서도 GoogleService-Info.plist가 포함되는지 확인**

---

### 7. 문제 해결 체크리스트

#### 7.1 푸시 알림이 수신되지 않는 경우
- [ ] **APNs 인증 키/인증서가 Firebase에 올바르게 업로드되었는지 확인**
- [ ] **Bundle ID가 Apple Developer, Firebase, Xcode에서 모두 일치하는지 확인**
- [ ] **앱이 실제 기기에서 실행되고 있는지 확인** (시뮬레이터는 푸시 알림 미지원)
- [ ] **푸시 알림 권한이 허용되었는지 확인** (설정 → 알림)
- [ ] **FCM 토큰이 올바르게 생성되고 백엔드로 전송되었는지 확인**
- [ ] **백엔드에서 FCM API 호출이 성공하는지 확인** (로그 확인)
- [ ] **앱이 백그라운드에 있는지 확인** (포그라운드/백그라운드 처리 다름)

#### 7.2 FCM 토큰이 생성되지 않는 경우
- [ ] **Firebase 초기화 코드가 실행되는지 확인** (`FirebaseApp.configure()`)
- [ ] **GoogleService-Info.plist가 프로젝트에 포함되어 있는지 확인**
- [ ] **GoogleService-Info.plist의 Target Membership이 올바른지 확인**
- [ ] **APNs 토큰 등록이 성공했는지 확인** (`didRegisterForRemoteNotificationsWithDeviceToken`)
- [ ] **네트워크 연결이 정상인지 확인**

#### 7.3 Release 빌드에서 작동하지 않는 경우
- [ ] **GoogleService-Info.plist가 Release 빌드에 포함되는지 확인**
- [ ] **Release 빌드의 Bundle ID가 올바른지 확인**
- [ ] **Release 빌드의 Provisioning Profile에 Push Notifications이 포함되는지 확인**
- [ ] **Firebase SDK가 Release 빌드에 포함되는지 확인**

---

### 8. 배포 전 최종 확인 사항

- [ ] Apple Developer Portal에서 App ID에 Push Notifications 활성화됨
- [ ] APNs 인증 키/인증서가 Firebase에 업로드됨
- [ ] Firebase 프로젝트에 iOS 앱이 등록됨
- [ ] GoogleService-Info.plist가 프로젝트에 포함됨
- [ ] Xcode에서 Push Notifications Capability 활성화됨
- [ ] Bundle ID가 모든 곳에서 일치함
- [ ] Firebase 초기화 코드가 구현됨
- [ ] 푸시 알림 권한 요청 코드가 구현됨
- [ ] FCM 토큰 수신 및 백엔드 전송 코드가 구현됨
- [ ] 푸시 알림 수신 처리 코드가 구현됨
- [ ] 백엔드 환경 변수가 올바르게 설정됨
- [ ] 실제 기기에서 테스트 완료됨
- [ ] Release 빌드에서 테스트 완료됨

---

## 📚 참고 자료

- [Apple Push Notification Service 가이드](https://developer.apple.com/documentation/usernotifications)
- [Firebase Cloud Messaging iOS 가이드](https://firebase.google.com/docs/cloud-messaging/ios/client)
- [Firebase iOS 시작하기](https://firebase.google.com/docs/ios/setup)
- [Apple Developer Portal](https://developer.apple.com/account/)
- [Firebase Console](https://console.firebase.google.com/)

---

## 🔍 주요 확인 포인트 요약

1. **Apple Developer**: App ID에 Push Notifications 활성화, APNs 인증 키/인증서 생성
2. **Firebase**: iOS 앱 등록, APNs 인증 키 업로드, GoogleService-Info.plist 다운로드
3. **Xcode**: Firebase SDK 설치, Push Notifications Capability 활성화, Bundle ID 일치
4. **앱 코드**: Firebase 초기화, 권한 요청, FCM 토큰 수신 및 전송, 알림 수신 처리
5. **백엔드**: FCM 서비스 계정 키 설정, 푸시 알림 전송 API 구현
6. **테스트**: 실제 기기에서 테스트, Release 빌드에서 테스트

---

**마지막 업데이트**: 2024년

