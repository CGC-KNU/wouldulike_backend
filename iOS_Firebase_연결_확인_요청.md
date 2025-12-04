# iOS 앱 Firebase 연결 확인 요청

## 📋 개요

현재 Firebase 대시보드에서 iOS 앱(`wouldulikeios`)의 Analytics 데이터가 수집되지 않고 있습니다 (DAU: 0명). Android 앱은 정상적으로 작동 중이므로, iOS 앱의 Firebase 연결 상태를 확인해주시기 바랍니다.

## ✅ 확인 사항 체크리스트

다음 항목들을 순서대로 확인해주세요:

### 1. Firebase SDK 설치 확인

- [ ] **CocoaPods 사용 시**
  
  **1단계: CocoaPods 설치 확인**
  ```bash
  pod --version
  ```
  - CocoaPods가 설치되어 있지 않다면 설치:
    ```bash
    sudo gem install cocoapods
    ```
  
  **2단계: Podfile 생성 및 설정**
  
  **Podfile 위치:**
  - Podfile은 **iOS 프로젝트의 루트 디렉토리**에 있습니다
  - 일반적인 프로젝트 구조:
    ```
    your-ios-project/
    ├── Podfile          ← 여기에 있음!
    ├── Podfile.lock    ← pod install 후 생성됨
    ├── Pods/           ← pod install 후 생성됨
    ├── YourApp.xcodeproj
    └── YourApp/
        ├── AppDelegate.swift
        ├── ViewController.swift
        └── ...
    ```
  
  **Podfile 찾기:**
  ```bash
  cd /path/to/ios/project  # iOS 프로젝트 디렉토리로 이동
  
  # Podfile이 있는지 확인
  ls -la | grep Podfile
  
  # 결과 해석:
  # - Podfile이 보이면 → Podfile이 존재함
  # - 아무것도 안 뜨면 → Podfile이 없음 (아래 "Podfile 생성" 단계로 진행)
  
  # 또는 직접 확인
  ls Podfile  # 파일이 있으면 파일 정보가 보이고, 없으면 "No such file" 에러
  ```
  
  **Podfile이 없다면 생성:**
  
  ⚠️ **중요: `pod init` 실행 전에 올바른 디렉토리에 있는지 확인해야 합니다!**
  
  **1단계: Xcode 프로젝트 파일 확인**
  ```bash
  # 현재 디렉토리 확인
  pwd
  
  # .xcodeproj 파일이 있는지 확인
  ls *.xcodeproj
  
  # 또는
  find . -name "*.xcodeproj" -type d
  ```
  
  **에러 발생 시: `[!] no Xcode project found`**
  
  이 에러는 현재 디렉토리에 `.xcodeproj` 파일이 없다는 의미입니다.
  
  **해결 방법:**
  
  **방법 1: 올바른 디렉토리로 이동**
  ```bash
  # 1. Xcode 프로젝트 파일 찾기
  find ~ -name "*.xcodeproj" -type d 2>/dev/null | grep wouldulike
  
  # 2. 찾은 경로로 이동
  cd /path/to/found/project
  
  # 3. .xcodeproj 파일 확인
  ls *.xcodeproj
  
  # 4. 이제 pod init 실행
  pod init
  ```
  
  **방법 2: Xcode에서 프로젝트 위치 확인**
  1. Xcode에서 프로젝트 열기
  2. 프로젝트 네비게이터에서 프로젝트 파일 우클릭
  3. "Show in Finder" 선택
  4. Finder에서 열린 폴더가 프로젝트 루트 디렉토리입니다
  5. 터미널에서 해당 경로로 이동:
     ```bash
     cd /path/shown/in/finder
     pod init
     ```
  
  **방법 3: 현재 디렉토리 구조 확인**
  ```bash
  # 현재 디렉토리의 모든 파일/폴더 확인
  ls -la
  
  # 하위 디렉토리 확인
  ls -d */
  
  # Xcode 프로젝트가 하위 폴더에 있을 수 있음
  # 예: ios/wouldulikeios.xcodeproj
  cd ios  # 또는 다른 하위 폴더
  ls *.xcodeproj
  ```
  
  **2단계: Podfile 생성**
  ```bash
  # .xcodeproj 파일이 있는 디렉토리에서 실행
  pod init
  
  # 생성 확인
  ls -la | grep Podfile  # 이제 Podfile이 보여야 함
  
  # 생성된 Podfile 내용 확인
  cat Podfile
  ```
  
  **3단계: Podfile 편집**
  - 생성된 Podfile을 열어서 Firebase SDK 추가
  
  **3단계: Podfile 편집**
  - `Podfile` 파일을 열어서 다음 내용 추가:
    ```ruby
    platform :ios, '13.0'  # 최소 iOS 버전 (프로젝트에 맞게 수정)
    
    target 'YourAppName' do  # 앱 타겟 이름으로 변경
      use_frameworks!
      
      # Firebase SDK 추가
      pod 'Firebase/Analytics'
      pod 'Firebase/Messaging'  # 푸시 알림 사용 시
      # 필요에 따라 다른 Firebase 모듈 추가 가능:
      # pod 'Firebase/Auth'
      # pod 'Firebase/Firestore'
      # pod 'Firebase/Storage'
    end
    ```
  
  **4단계: Firebase SDK 설치**
  ```bash
  pod install
  ```
  - 설치 완료 후 `.xcworkspace` 파일을 사용하여 프로젝트 열기
  - 주의: `.xcodeproj`가 아닌 `.xcworkspace` 파일을 열어야 함
  
  **5단계: 설치 확인**
  
  **Podfile이 있다고 해서 Firebase가 설치된 것은 아닙니다!**
  
  **설치 여부 확인 방법:**
  ```bash
  cd new1/ios  # Podfile이 있는 디렉토리로 이동
  
  # 1. Podfile 내용 확인 (Firebase가 추가되어 있는지)
  cat Podfile | grep Firebase
  
  # 결과 해석:
  # - Firebase 관련 줄이 보이면 → Podfile에 Firebase가 추가됨
  # - 아무것도 안 뜨면 → Podfile에 Firebase가 없음 (추가 필요)
  
  # 2. Podfile.lock 파일 확인 (실제 설치 여부)
  ls Podfile.lock
  
  # 결과 해석:
  # - 파일이 있으면 → pod install이 실행된 적이 있음
  # - 파일이 없으면 → pod install이 한 번도 실행되지 않음
  
  # 3. Podfile.lock에 Firebase가 있는지 확인
  cat Podfile.lock | grep Firebase
  
  # 결과 해석:
  # - Firebase 관련 내용이 보이면 → Firebase가 설치됨 ✅
  # - 아무것도 안 뜨면 → Firebase가 설치되지 않음 ❌
  
  # 4. Pods 디렉토리 확인
  ls -d Pods/
  
  # 결과 해석:
  # - Pods/ 디렉토리가 있으면 → pod install이 실행된 적이 있음
  # - 없으면 → pod install이 한 번도 실행되지 않음
  
  # 5. Pods 디렉토리에 Firebase가 있는지 확인
  ls Pods/ | grep Firebase
  
  # 결과 해석:
  # - Firebase 관련 폴더가 보이면 → Firebase가 설치됨 ✅
  # - 없으면 → Firebase가 설치되지 않음 ❌
  ```
  
  **설치 상태 판단:**
  
  | 항목 | 상태 | 의미 |
  |------|------|------|
  | Podfile 존재 | ✅ | CocoaPods 설정됨 |
  | Podfile에 Firebase 추가 | ❓ | 확인 필요 |
  | Podfile.lock 존재 | ❓ | 확인 필요 |
  | Podfile.lock에 Firebase | ❓ | 확인 필요 |
  | Pods/ 디렉토리 존재 | ❓ | 확인 필요 |
  | Pods/에 Firebase | ✅ | **Firebase 설치됨** |
  
  **Firebase가 설치되지 않은 경우:**
  1. Podfile에 Firebase 추가 (3단계 참고)
  2. `pod install` 실행
  3. 다시 확인

- [ ] **Swift Package Manager (SPM) 사용 시**
  
  **터미널에서 직접 설치하는 방법은 없고, Xcode에서 GUI로 설치해야 합니다:**
  
  1. Xcode에서 프로젝트 열기
  2. 프로젝트 네비게이터에서 프로젝트 파일 선택
  3. TARGETS → 프로젝트 타겟 선택
  4. "Package Dependencies" 탭 클릭
  5. "+" 버튼 클릭
  6. 패키지 URL 입력: `https://github.com/firebase/firebase-ios-sdk`
  7. 버전 선택 (최신 버전 권장)
  8. "Add Package" 클릭
  9. 필요한 Firebase 제품 선택:
     - Firebase Analytics
     - Firebase Cloud Messaging (푸시 알림 사용 시)
     - 기타 필요한 제품들
  10. "Add Package" 클릭하여 설치 완료
  
  **또는 Package.swift 파일 사용 (Swift Package Manager 프로젝트인 경우):**
  ```swift
  // Package.swift
  dependencies: [
      .package(url: "https://github.com/firebase/firebase-ios-sdk", from: "10.0.0")
  ],
  targets: [
      .target(
          name: "YourTarget",
          dependencies: [
              .product(name: "FirebaseAnalytics", package: "firebase-ios-sdk"),
              .product(name: "FirebaseMessaging", package: "firebase-ios-sdk")
          ]
      )
  ]
  ```

### 2. GoogleService-Info.plist 파일 확인

- [0] **파일 존재 여부**
  - `GoogleService-Info.plist` 파일이 프로젝트에 포함되어 있는지 확인
  - Firebase Console에서 다운로드한 최신 파일인지 확인
  - 다운로드 경로: Firebase Console → 프로젝트 설정 → iOS 앱 → GoogleService-Info.plist 다운로드

- [0] **파일 위치 확인**
  - 프로젝트 루트 디렉토리에 위치해야 함
  - Xcode 프로젝트 네비게이터에서 파일이 보이는지 확인
  - Target Membership에 해당 앱 타겟이 체크되어 있는지 확인

- [0] **파일 내용 확인**
  - `PROJECT_ID`가 현재 Firebase 프로젝트 ID와 일치하는지 확인
  - `BUNDLE_ID`가 앱의 번들 ID(`com.coggiri.wouldulike0117`)와 일치하는지 확인

### 3. Firebase 초기화 코드 확인

- [ ] **AppDelegate.swift 또는 App.swift에서 초기화 코드 확인**

  **SwiftUI vs UIKit 구분 방법:**
  
  프로젝트가 SwiftUI를 사용하는지 UIKit을 사용하는지 확인하는 방법:
  
  **📌 쉬운 확인 방법 (단계별):**
  
  **1단계: 프로젝트 디렉토리로 이동**
  ```bash
  cd new1/ios
  pwd  # 현재 위치 확인
  ```
  
  **2단계: 모든 Swift 파일 목록 보기**
  ```bash
  # 모든 .swift 파일 찾기
  find . -name "*.swift" -type f | head -20
  
  # 또는 더 간단하게
  ls -R | grep "\.swift$"
  ```
  
  **3단계: App 관련 파일 찾기**
  ```bash
  # App으로 시작하는 모든 파일 찾기
  find . -name "App*.swift" -type f
  
  # 또는 대소문자 구분 없이
  find . -iname "app*.swift" -type f
  
  # 결과 예시:
  # ./wouldulikeios/App.swift
  # ./wouldulikeios/AppDelegate.swift
  ```
  
  **4단계: 파일 내용 확인 (파일이 있을 때)**
  ```bash
  # App.swift 파일이 있다면
  cat ./wouldulikeios/App.swift
  
  # AppDelegate.swift 파일이 있다면
  cat ./wouldulikeios/AppDelegate.swift
  ```
  
  **5단계: import 문으로 확인 (가장 확실한 방법)**
  ```bash
  # 모든 Swift 파일에서 SwiftUI import 찾기
  grep -r "import SwiftUI" . --include="*.swift"
  
  # 모든 Swift 파일에서 UIKit import 찾기
  grep -r "import UIKit" . --include="*.swift"
  
  # 결과 해석:
  # - "import SwiftUI"가 여러 파일에서 보이면 → SwiftUI 사용 중
  # - "import UIKit"만 보이면 → UIKit 사용 중
  ```
  
  **방법 1: 파일 존재 여부로 확인 (상세)**
  ```bash
  cd new1/ios
  
  # App.swift 파일이 있으면 → SwiftUI
  find . -name "App.swift" -type f
  
  # AppDelegate.swift 파일이 있으면 → UIKit (또는 SwiftUI + UIKit 혼합)
  find . -name "AppDelegate.swift" -type f
  
  # 둘 다 확인
  find . -name "App*.swift" -type f
  ```
  
  **💡 파일을 찾지 못할 때:**
  
  만약 위 명령어로 파일을 찾지 못한다면:
  
  1. **현재 위치 확인:**
     ```bash
     pwd
     ls -la
     ```
  
  2. **상위/하위 디렉토리 확인:**
     ```bash
     # 상위 디렉토리로 이동
     cd ..
     ls -la
     
     # 또는 하위 디렉토리 확인
     ls -R | grep -i "app"
     ```
  
  3. **Xcode에서 직접 확인 (가장 확실):**
     - Xcode에서 프로젝트 열기
     - 왼쪽 프로젝트 네비게이터에서 파일 목록 확인
     - `App.swift` 또는 `AppDelegate.swift` 파일 찾기
  
  **방법 2: 파일 내용으로 확인**
  
  **App.swift 파일이 있고 내용이 다음과 같으면 → SwiftUI:**
  ```swift
  import SwiftUI
  
  @main
  struct YourApp: App {
      var body: some Scene {
          WindowGroup {
              ContentView()
          }
      }
  }
  ```
  
  **AppDelegate.swift 파일이 있고 내용이 다음과 같으면 → UIKit:**
  ```swift
  import UIKit
  
  @UIApplicationMain
  class AppDelegate: UIResponder, UIApplicationDelegate {
      // ...
  }
  ```
  
  **방법 3: Xcode 프로젝트에서 확인**
  1. Xcode에서 프로젝트 열기
  2. 프로젝트 네비게이터에서 확인:
     - `App.swift` 파일이 있으면 → SwiftUI
     - `AppDelegate.swift` 파일만 있으면 → UIKit
     - 둘 다 있으면 → SwiftUI + UIKit 혼합 (AppDelegate는 보통 설정용)
  
  **방법 4: Info.plist에서 확인**
  
  ⚠️ **Info.plist 파일 위치:**
  - 최신 Xcode 프로젝트에서는 Info.plist가 프로젝트 설정에 통합되어 파일로 보이지 않을 수 있습니다
  - 또는 여러 위치에 있을 수 있습니다
  
  ```bash
  cd new1/ios
  
  # Info.plist 파일 찾기 (모든 위치)
  find . -name "Info.plist" -type f
  
  # 또는 더 넓게 찾기
  find . -name "*Info*.plist" -type f
  
  # 결과 해석:
  # - 파일이 여러 개 나올 수 있음 (타겟별로 다를 수 있음)
  # - 예: wouldulikeios/Info.plist, wouldulikeiosTests/Info.plist 등
  ```
  
  **Info.plist 파일이 없는 경우:**
  - 최신 Xcode 프로젝트는 Info.plist를 프로젝트 설정에 통합했을 수 있습니다
  - 이 경우 다른 방법으로 확인하는 것이 더 확실합니다
  
  **Info.plist 파일이 있는 경우:**
  ```bash
  # 찾은 Info.plist 파일 확인
  # 예: ./wouldulikeios/Info.plist
  cat ./wouldulikeios/Info.plist | grep -i "UIScene"
  
  # 또는 plutil로 읽기 (macOS)
  plutil -p ./wouldulikeios/Info.plist | grep -i "UIScene"
  ```
  
  **결과 해석:**
  - `UIScene` 관련 설정이 있으면 → UIKit (Scene-based 앱)
  - 없으면 → SwiftUI 또는 구버전 UIKit
  
  **더 확실한 방법:**
  - Info.plist가 없거나 찾기 어려우면, 위의 방법 1, 2, 3을 사용하는 것이 더 확실합니다
  
  **방법 5: 소스 코드에서 확인**
  ```bash
  # SwiftUI import가 있는 파일 찾기
  grep -r "import SwiftUI" . --include="*.swift"
  
  # UIKit import가 있는 파일 찾기
  grep -r "import UIKit" . --include="*.swift"
  ```
  - `import SwiftUI`가 많으면 → SwiftUI 프로젝트
  - `import UIKit`만 있으면 → UIKit 프로젝트
  
  **결과 해석:**
  - ✅ `App.swift` 파일 존재 + `@main struct App` → **SwiftUI**
  - ✅ `AppDelegate.swift` 파일 존재 + `@UIApplicationMain` → **UIKit**
  - ✅ 둘 다 있으면 → **SwiftUI + UIKit 혼합** (최신 프로젝트는 보통 이 경우)
  
  **초기화 코드의 목적:**
  
  `FirebaseApp.configure()`는 Firebase SDK를 사용하기 전에 **반드시 호출해야 하는 필수 코드**입니다.
  
  **주요 역할:**
  1. **GoogleService-Info.plist 파일 읽기**
     - Firebase 프로젝트 설정 정보를 로드합니다
     - 프로젝트 ID, API 키, 번들 ID 등을 읽어옵니다
     - 이 정보 없이는 Firebase 서비스에 연결할 수 없습니다
  
  2. **Firebase 서비스 초기화**
     - Analytics, Cloud Messaging, Auth 등 모든 Firebase 서비스를 준비합니다
     - 각 서비스가 정상적으로 작동할 수 있도록 설정합니다
  
  3. **앱과 Firebase 프로젝트 연결**
     - 앱이 어떤 Firebase 프로젝트에 연결될지 결정합니다
     - GoogleService-Info.plist의 PROJECT_ID를 사용하여 연결합니다
  
  4. **SDK 활성화**
     - Firebase SDK의 모든 기능을 사용 가능한 상태로 만듭니다
     - 초기화 없이는 Firebase 기능이 전혀 작동하지 않습니다
  
  **초기화 코드가 없으면:**
  - ❌ Firebase Analytics가 데이터를 수집하지 않음
  - ❌ 푸시 알림이 작동하지 않음
  - ❌ Firebase Console에 앱 데이터가 나타나지 않음
  - ❌ 모든 Firebase 기능이 비활성화됨
  
  **초기화 코드가 있으면:**
  - ✅ Firebase Analytics가 자동으로 앱 사용 데이터를 수집
  - ✅ 푸시 알림을 받을 수 있음
  - ✅ Firebase Console에서 앱 데이터 확인 가능
  - ✅ 모든 Firebase 기능 사용 가능
  
  **파일 위치:**
  
  Firebase 초기화 코드는 다음 파일 중 하나에 있어야 합니다:
  
  **SwiftUI 프로젝트인 경우:**
  ```
  your-ios-project/
  └── YourApp/
      └── App.swift          ← 여기에 있음!
  ```
  
  **UIKit 프로젝트인 경우:**
  ```
  your-ios-project/
  └── YourApp/
      └── AppDelegate.swift  ← 여기에 있음!
  ```
  
  **파일 찾기 방법:**
  ```bash
  cd new1/ios  # 또는 프로젝트 디렉토리
  
  # App.swift 찾기 (SwiftUI)
  find . -name "App.swift" -type f
  
  # AppDelegate.swift 찾기 (UIKit)
  find . -name "AppDelegate.swift" -type f
  
  # 또는 둘 다 찾기
  find . -name "App*.swift" -type f
  ```
  
  **일반적인 위치:**
  - 프로젝트 루트의 앱 소스 코드 폴더 안
  - 예: `new1/ios/wouldulikeios/App.swift`
  - 예: `new1/ios/wouldulikeios/AppDelegate.swift`
  - 또는 Xcode 프로젝트 네비게이터에서 확인 가능

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

## 🚨 배포 후에도 사용자 수가 0명인 경우 - 추가 진단

배포 후에도 Firebase 콘솔에 사용자 수가 0명으로 표시되는 경우, 다음 항목들을 추가로 확인해야 합니다:

### ⚠️ 중요: 배포 환경 확인

**1. 실제 배포 확인**
- [ ] 앱이 실제로 TestFlight 또는 App Store에 배포되었는지 확인
- [ ] 실제 사용자가 앱을 다운로드하고 실행했는지 확인
- [ ] 개발 빌드가 아닌 프로덕션 빌드로 배포되었는지 확인

**2. GoogleService-Info.plist 빌드 포함 확인**

⚠️ **가장 흔한 원인: GoogleService-Info.plist가 빌드에 포함되지 않음**

**확인 방법:**
1. Xcode에서 프로젝트 열기
2. 프로젝트 네비게이터에서 `GoogleService-Info.plist` 파일 선택
3. 오른쪽 패널에서 "Target Membership" 확인
4. **앱 타겟에 체크가 되어 있는지 확인** (예: `wouldulikeios`)

**문제 발견 시 해결:**
1. `GoogleService-Info.plist` 파일 선택
2. File Inspector (오른쪽 패널) 열기
3. "Target Membership" 섹션에서 앱 타겟 체크박스 활성화
4. 다시 빌드 및 배포

**빌드 스크립트로 확인 (고급):**
```bash
# 앱 번들 내부에 GoogleService-Info.plist가 포함되어 있는지 확인
# 실제 기기나 시뮬레이터에서 앱 실행 후:
xcrun simctl get_app_container booted com.coggiri.wouldulike0117

# 또는 앱 번들 내용 확인:
unzip -l /path/to/YourApp.app | grep GoogleService
```

**3. 번들 ID 확인**

**확인 방법:**
1. Xcode에서 프로젝트 선택
2. TARGETS → 앱 타겟 선택
3. "General" 탭 → "Bundle Identifier" 확인
4. **반드시 `com.coggiri.wouldulike0117`과 일치해야 함**

**GoogleService-Info.plist의 번들 ID 확인:**
```bash
# GoogleService-Info.plist 파일에서 번들 ID 확인
plutil -p GoogleService-Info.plist | grep BUNDLE_ID

# 또는
cat GoogleService-Info.plist | grep -A 1 BUNDLE_ID
```

**4. Firebase Console에서 앱 등록 확인**

**확인 방법:**
1. Firebase Console 접속
2. 프로젝트 설정 → "내 앱" 섹션 확인
3. iOS 앱(`wouldulikeios`)이 등록되어 있는지 확인
4. 번들 ID가 `com.coggiri.wouldulike0117`로 등록되어 있는지 확인

**5. Debug vs Release 빌드 설정**

**문제:**
- Debug 빌드에서는 작동하지만 Release 빌드에서는 작동하지 않을 수 있음
- 특히 GoogleService-Info.plist가 Debug 타겟에만 포함된 경우
- **개발 모드에서 FCM 토큰이 정상이었다면, 이 문제일 가능성이 매우 높습니다**

**확인 방법:**
1. Xcode → Product → Scheme → Edit Scheme
2. "Run" → "Build Configuration" 확인
3. "Archive" → "Build Configuration" 확인
4. 둘 다 "Release"로 설정되어 있는지 확인

**해결 방법:**
1. **Release 빌드로 직접 테스트:**
   - Xcode → Product → Scheme → Edit Scheme
   - "Run" → Build Configuration을 "Release"로 변경
   - 실제 기기에서 실행
   - FCM 토큰과 Analytics 이벤트 모두 확인

2. **GoogleService-Info.plist가 모든 빌드 설정에 포함되는지 확인:**
   - 파일 선택 → File Inspector
   - Target Membership에서 앱 타겟 체크 확인
   - Build Phases → Copy Bundle Resources에 포함 확인

3. **Archive 빌드에서 확인:**
   - Product → Archive
   - Archive 생성 후 "Distribute App"
   - Export된 앱 번들에서 GoogleService-Info.plist 포함 여부 확인

**6. Firebase 초기화 코드 실행 확인**

**디버깅 코드 추가:**
```swift
// App.swift 또는 AppDelegate.swift에 추가
import Firebase
import FirebaseAnalytics

// SwiftUI 사용 시
@main
struct YourApp: App {
    init() {
        print("🔥 Firebase 초기화 시작...")
        FirebaseApp.configure()
        print("✅ Firebase 초기화 완료")
        
        // 테스트 이벤트 전송
        Analytics.logEvent("app_initialized", parameters: nil)
        print("📊 테스트 이벤트 전송 완료")
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

// UIKit 사용 시
func application(_ application: UIApplication, 
                didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    print("🔥 Firebase 초기화 시작...")
    FirebaseApp.configure()
    print("✅ Firebase 초기화 완료")
    
    // 테스트 이벤트 전송
    Analytics.logEvent("app_initialized", parameters: nil)
    print("📊 테스트 이벤트 전송 완료")
    
    return true
}
```

**Xcode 콘솔에서 확인:**
- 앱 실행 시 위의 로그 메시지가 출력되는지 확인
- 에러 메시지가 있다면 내용 확인

**7. 네트워크 연결 및 권한 확인**

**확인 사항:**
- [ ] 앱이 인터넷 연결 권한을 요청하는지 확인
- [ ] 실제 기기에서 Wi-Fi 또는 셀룰러 데이터 연결 확인
- [ ] 방화벽이나 VPN이 Firebase 서버 접근을 차단하지 않는지 확인

**8. FCM은 작동하지만 Analytics만 작동하지 않는 경우**

**증상:**
- 개발 모드에서 FCM 토큰이 정상적으로 표시됨 ✅
- 하지만 Firebase Analytics 사용자 수가 0명 ❌

**가능한 원인:**

**1. Analytics SDK가 포함되지 않음**
- FCM은 작동하지만 Analytics SDK가 Release 빌드에 포함되지 않았을 수 있음

**확인 방법:**
```bash
# Podfile 확인
cat Podfile | grep Analytics

# Podfile.lock 확인
cat Podfile.lock | grep Analytics

# Pods 디렉토리 확인
ls Pods/ | grep Analytics
```

**해결 방법:**
- Podfile에 `pod 'Firebase/Analytics'` 추가 확인
- `pod install` 재실행
- Clean Build 후 다시 빌드

**2. Analytics가 명시적으로 비활성화됨**
- 코드에서 Analytics를 비활성화했을 수 있음

**확인 방법:**
```swift
// App.swift 또는 AppDelegate.swift에서 확인
// 다음 코드가 있는지 확인:
Analytics.setAnalyticsCollectionEnabled(false)  // ← 이 코드가 있으면 문제!
```

**해결 방법:**
- 위 코드가 있다면 제거하거나 `true`로 변경
- 또는 조건부로만 비활성화되어 있는지 확인

**3. Info.plist 설정 문제**
- Analytics 관련 설정이 비활성화되어 있을 수 있음

**확인 방법:**
- Info.plist에서 다음 키 확인:
  ```xml
  <key>FIREBASE_ANALYTICS_COLLECTION_ENABLED</key>
  <false/>  <!-- ← false면 문제! -->
  ```

**해결 방법:**
- 위 키를 `true`로 변경하거나 제거
- 또는 프로젝트 설정에서 확인

**4. Release 빌드 최적화 문제**
- 컴파일러 최적화로 인해 Analytics 코드가 제거되었을 수 있음

**확인 방법:**
- Xcode → TARGETS → 앱 타겟 → Build Settings
- "Optimization Level" 확인
- "Swift Compiler - Code Generation" → "Optimization Level" 확인

**해결 방법:**
- Release 빌드에서도 Analytics 코드가 제거되지 않도록 설정 확인

**9. Firebase Analytics 지연 시간**

**중요:**
- Firebase Analytics 데이터는 **실시간이 아닙니다**
- 일반적으로 **24-48시간** 후에 대시보드에 반영됩니다
- 실시간 이벤트는 Firebase Console → Analytics → 실시간 이벤트에서 확인 가능

**확인 방법:**
1. Firebase Console → Analytics → 실시간 이벤트
2. 앱 실행 후 몇 분 내에 이벤트가 보이는지 확인
3. 실시간 이벤트가 보이면 → 설정은 정상, 대시보드 반영만 대기 중
4. 실시간 이벤트도 안 보이면 → 설정 문제 가능성 높음

**9. 앱 버전 및 빌드 번호 확인**

**확인 방법:**
1. Firebase Console → Analytics → 사용자 속성
2. 앱 버전별 사용자 수 확인
3. 배포한 버전과 Firebase에 기록된 버전이 일치하는지 확인

**10. 추가 디버깅: Firebase Analytics 디버그 모드**

**활성화 방법:**
1. Xcode에서 Scheme 편집
2. "Run" → "Arguments" 탭
3. "Arguments Passed On Launch"에 추가:
   ```
   -FIRDebugEnabled
   ```
4. 또는 터미널에서:
   ```bash
   # 시뮬레이터 실행 시
   xcrun simctl launch --console booted com.coggiri.wouldulike0117
   ```

**확인 사항:**
- Firebase Analytics 디버그 로그가 출력되는지 확인
- 이벤트 전송 성공/실패 메시지 확인

**11. GoogleService-Info.plist 파일 경로 확인**

**문제:**
- 파일이 프로젝트에 추가되었지만, 빌드 시 올바른 위치에 복사되지 않을 수 있음

**확인 방법:**
1. Xcode 프로젝트 네비게이터에서 `GoogleService-Info.plist` 선택
2. File Inspector에서 "Location" 확인
3. 파일이 프로젝트 루트 디렉토리에 있는지 확인
4. "Full Path"가 프로젝트 내부 경로인지 확인

**12. CocoaPods 사용 시 .xcworkspace 파일 사용 확인**

**중요:**
- CocoaPods를 사용하는 경우, 반드시 `.xcworkspace` 파일로 프로젝트를 열어야 함
- `.xcodeproj` 파일로 열면 Firebase SDK를 찾을 수 없음

**확인 방법:**
```bash
cd /path/to/ios/project

# .xcworkspace 파일이 있는지 확인
ls *.xcworkspace

# 있다면 이 파일로 프로젝트 열기
open YourApp.xcworkspace
```

**13. Firebase 프로젝트 설정 확인**

**Firebase Console에서 확인:**
1. Firebase Console → 프로젝트 설정
2. "일반" 탭 → "내 앱" 섹션
3. iOS 앱이 올바른 번들 ID로 등록되어 있는지 확인
4. "GoogleService-Info.plist" 다운로드 버튼이 있는지 확인

**14. 실제 기기에서 테스트**

**중요:**
- 시뮬레이터에서도 작동하지만, 실제 기기에서 테스트하는 것이 더 확실함
- 특히 네트워크 연결 및 권한 관련 문제를 확인할 수 있음

**테스트 방법:**
1. 실제 iOS 기기에 앱 설치
2. 앱 실행
3. Xcode → Window → Devices and Simulators
4. 기기 선택 → "Open Console" 클릭
5. Firebase 관련 로그 확인

### 📋 체크리스트 요약

배포 후 사용자 수가 0명인 경우 다음을 확인하세요:

- [ ] **GoogleService-Info.plist가 Target Membership에 포함되어 있는가?**
- [ ] **번들 ID가 `com.coggiri.wouldulike0117`과 정확히 일치하는가?**
- [ ] **Firebase 초기화 코드가 실제로 실행되는가? (로그 확인)**
- [ ] **실제 사용자가 앱을 실행했는가?**
- [ ] **Firebase Console → 실시간 이벤트에서 이벤트가 보이는가?**
- [ ] **앱이 Release 빌드로 배포되었는가?**
- [ ] **.xcworkspace 파일로 프로젝트를 열었는가? (CocoaPods 사용 시)**
- [ ] **Firebase Console에 iOS 앱이 올바르게 등록되어 있는가?**

### 🎯 개발 모드에서 FCM 토큰이 정상이었던 경우 - 우선 확인 사항

**개발 모드에서 FCM 토큰이 정상적으로 표시되었다면, 다음 항목들을 우선적으로 확인하세요:**

#### 1. Release 빌드 설정 확인 (가장 중요!)

- [ ] **GoogleService-Info.plist가 Release 빌드에 포함되는지 확인**
  1. Xcode → 프로젝트 선택
  2. TARGETS → 앱 타겟 선택
  3. Build Phases → Copy Bundle Resources
  4. `GoogleService-Info.plist`가 목록에 있는지 확인

- [ ] **Release 빌드로 직접 테스트**
  1. Xcode → Product → Scheme → Edit Scheme
  2. "Run" → Build Configuration을 "Release"로 변경
  3. 실제 기기에서 실행
  4. FCM 토큰과 Analytics 이벤트 모두 확인

- [ ] **Archive 빌드에서 GoogleService-Info.plist 포함 확인**
  1. Product → Archive
  2. Archive 생성 후 Export
  3. Export된 앱 번들에서 파일 포함 여부 확인

#### 2. Analytics SDK 포함 확인

- [ ] **Podfile에 Analytics 포함 확인**
  ```bash
  cat Podfile | grep Analytics
  # 또는
  cat Podfile | grep Firebase/Analytics
  ```

- [ ] **Podfile.lock에 Analytics 포함 확인**
  ```bash
  cat Podfile.lock | grep Analytics
  ```

- [ ] **Pods 디렉토리에 Analytics 확인**
  ```bash
  ls Pods/ | grep Analytics
  ```

#### 3. Analytics 비활성화 코드 확인

- [ ] **코드에서 Analytics가 비활성화되지 않았는지 확인**
  ```swift
  // 다음 코드가 있는지 확인:
  Analytics.setAnalyticsCollectionEnabled(false)  // ← 있으면 문제!
  ```

- [ ] **Info.plist에서 Analytics 비활성화 확인**
  ```xml
  <!-- 다음 키가 false로 설정되어 있지 않은지 확인 -->
  <key>FIREBASE_ANALYTICS_COLLECTION_ENABLED</key>
  <false/>  <!-- ← false면 문제! -->
  ```

#### 4. Firebase Console 실시간 이벤트 확인

- [ ] **실시간 이벤트에서 이벤트가 보이는지 확인**
  1. Firebase Console → Analytics → 실시간 이벤트
  2. 앱 실행 후 몇 분 내에 이벤트 확인
  3. 실시간 이벤트가 보이면 → 설정 정상, 대시보드 반영만 대기
  4. 실시간 이벤트도 안 보이면 → Release 빌드 설정 문제 가능성 높음

#### 5. 빌드 스크립트 확인

- [ ] **빌드 스크립트에서 GoogleService-Info.plist가 제거되지 않는지 확인**
  1. Xcode → TARGETS → 앱 타겟 → Build Phases
  2. "Run Script" 섹션 확인
  3. GoogleService-Info.plist를 제거하는 스크립트가 있는지 확인

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

