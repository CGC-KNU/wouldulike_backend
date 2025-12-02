# iOS 앱 Firebase 연결 확인 요청

## 📋 개요

현재 Firebase 대시보드에서 iOS 앱(`wouldulikeios`)의 Analytics 데이터가 수집되지 않고 있습니다 (DAU: 0명). Android 앱은 정상적으로 작동 중이므로, iOS 앱의 Firebase 연결 상태를 확인해주시기 바랍니다.

## ✅ 확인 사항 체크리스트

다음 항목들을 순서대로 확인해주세요:

### 1. Firebase SDK 설치 확인

- [ ] **CocoaPods 사용 시**
  - `Podfile`에 Firebase 관련 pod이 추가되어 있는지 확인
  - 예시:
    ```ruby
    pod 'Firebase/Analytics'
    pod 'Firebase/Messaging'  # 푸시 알림 사용 시
    ```
  - `pod install` 또는 `pod update` 실행 여부 확인
  - `Podfile.lock` 파일에 Firebase가 포함되어 있는지 확인

- [ ] **Swift Package Manager (SPM) 사용 시**
  - Xcode → File → Add Package Dependencies
  - Firebase 패키지가 추가되어 있는지 확인
  - 패키지 URL: `https://github.com/firebase/firebase-ios-sdk`

### 2. GoogleService-Info.plist 파일 확인

- [ ] **파일 존재 여부**
  - `GoogleService-Info.plist` 파일이 프로젝트에 포함되어 있는지 확인
  - Firebase Console에서 다운로드한 최신 파일인지 확인
  - 다운로드 경로: Firebase Console → 프로젝트 설정 → iOS 앱 → GoogleService-Info.plist 다운로드

- [ ] **파일 위치 확인**
  - 프로젝트 루트 디렉토리에 위치해야 함
  - Xcode 프로젝트 네비게이터에서 파일이 보이는지 확인
  - Target Membership에 해당 앱 타겟이 체크되어 있는지 확인

- [ ] **파일 내용 확인**
  - `PROJECT_ID`가 현재 Firebase 프로젝트 ID와 일치하는지 확인
  - `BUNDLE_ID`가 앱의 번들 ID(`com.coggiri.wouldulike0117`)와 일치하는지 확인

### 3. Firebase 초기화 코드 확인

- [ ] **AppDelegate.swift 또는 App.swift에서 초기화 코드 확인**

  **SwiftUI 사용 시 (App.swift):**
  ```swift
  import SwiftUI
  import Firebase
  
  @main
  struct YourApp: App {
      init() {
          FirebaseApp.configure()  // ← 이 코드가 있어야 함
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
  
  @UIApplicationMain
  class AppDelegate: UIResponder, UIApplicationDelegate {
      
      func application(_ application: UIApplication, 
                      didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
          FirebaseApp.configure()  // ← 이 코드가 있어야 함
          return true
      }
      
      // ... 나머지 코드
  }
  ```

- [ ] **초기화 코드가 앱 시작 시점에 호출되는지 확인**
  - `FirebaseApp.configure()`가 앱의 가장 먼저 실행되는 코드 중 하나인지 확인
  - 다른 SDK 초기화보다 먼저 실행되는 것이 좋음

### 4. Firebase Analytics 활성화 확인

- [ ] **Info.plist 설정 확인**
  - `FirebaseAutomaticScreenReportingEnabled`가 `true`로 설정되어 있는지 확인 (선택사항)
  - 또는 수동으로 화면 추적 코드가 구현되어 있는지 확인

- [ ] **테스트 이벤트 전송 확인**
  - 앱 실행 후 Firebase Console에서 실시간 이벤트가 보이는지 확인
  - 또는 다음 코드로 테스트:
    ```swift
    import FirebaseAnalytics
    
    Analytics.logEvent("test_event", parameters: nil)
    ```

### 5. 빌드 및 실행 확인

- [ ] **클린 빌드 실행**
  - Xcode → Product → Clean Build Folder (Shift + Cmd + K)
  - 다시 빌드 및 실행

- [ ] **실제 기기에서 테스트**
  - 시뮬레이터가 아닌 실제 iOS 기기에서 테스트
  - Firebase Analytics는 시뮬레이터에서도 작동하지만, 실제 기기에서 확인하는 것이 더 확실함

- [ ] **앱 실행 후 Firebase Console 확인**
  - Firebase Console → Analytics → 대시보드
  - 앱 실행 후 몇 분 내에 데이터가 나타나는지 확인
  - 실시간 이벤트에서 앱 실행 이벤트가 보이는지 확인

## 🔍 문제 해결 가이드

### 문제 1: Firebase SDK가 설치되지 않음

**해결 방법:**
1. CocoaPods 사용 시:
   ```bash
   cd ios
   pod install
   ```
2. SPM 사용 시:
   - Xcode에서 패키지 의존성 다시 추가

### 문제 2: GoogleService-Info.plist 파일이 없음

**해결 방법:**
1. Firebase Console 접속
2. 프로젝트 설정 → iOS 앱 → GoogleService-Info.plist 다운로드
3. Xcode 프로젝트에 파일 추가 (드래그 앤 드롭)
4. Target Membership 체크 확인

### 문제 3: Firebase 초기화 코드가 없음

**해결 방법:**
1. `AppDelegate.swift` 또는 `App.swift` 파일 열기
2. 파일 상단에 `import Firebase` 추가
3. 앱 시작 메서드에 `FirebaseApp.configure()` 추가

### 문제 4: 빌드 에러 발생

**해결 방법:**
1. Xcode → Product → Clean Build Folder
2. Derived Data 삭제
3. CocoaPods 사용 시: `pod deintegrate && pod install`
4. 다시 빌드

## 📝 확인 완료 후 알려주실 내용

다음 항목들을 확인한 후 결과를 알려주시기 바랍니다:

1. ✅ **체크리스트 완료 여부**
   - 위의 체크리스트 중 어떤 항목이 문제였는지

2. 🔧 **수정한 내용**
   - 어떤 파일을 수정했는지
   - 어떤 코드를 추가/수정했는지

3. 🧪 **테스트 결과**
   - 앱 실행 후 Firebase Console에서 데이터가 보이는지
   - 에러 메시지가 있다면 내용

4. ❓ **추가 질문이나 문제점**
   - 확인 중 발견한 문제나 질문

## 📚 참고 자료

- [Firebase iOS 시작하기](https://firebase.google.com/docs/ios/setup)
- [Firebase Analytics iOS 가이드](https://firebase.google.com/docs/analytics/get-started?platform=ios)
- [Firebase Cloud Messaging iOS 가이드](https://firebase.google.com/docs/cloud-messaging/ios/client)

## ⚠️ 중요 사항

- **GoogleService-Info.plist 파일은 절대 Git에 커밋하지 마세요** (이미 .gitignore에 추가되어 있을 수 있음)
- Firebase 초기화는 앱의 가장 먼저 실행되는 코드 중 하나여야 합니다
- 실제 기기에서 테스트하는 것이 가장 확실합니다

---

**문의사항이 있으시면 언제든지 연락주세요!**

