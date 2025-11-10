# 마이페이지 계정정보에 카카오 ID 표시 요청

## 요구사항

마이페이지의 계정정보 섹션에서 '로그인', '로그아웃' 부분 아래에 사용자의 **카카오 ID**를 표시해주세요.

## 백엔드 API 변경 사항

로그인 API 응답에 `kakao_id` 필드가 추가되었습니다.

### 로그인 API 응답 형식

**엔드포인트**: `POST /api/auth/kakao`

**응답 예시**:
```json
{
  "token": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  },
  "user": {
    "id": 1,
    "kakao_id": 123456789,  // ✅ 새로 추가된 필드
    "nickname": "사용자닉네임",
    "profile_image_url": "https://..."
  },
  "is_new": false
}
```

### 변경된 필드

- `user.kakao_id`: 사용자의 카카오 ID (BigInteger, 숫자)

## 구현 요청 사항

### 1. UI 위치
- 마이페이지 > 계정정보 섹션
- '로그인' 또는 '로그아웃' 버튼 아래에 표시
- 예시 레이아웃:
  ```
  [계정정보]
  ┌─────────────────────┐
  │ 로그인 / 로그아웃    │
  │                     │
  │ 카카오 ID: 123456789│  ← 여기에 추가
  └─────────────────────┘
  ```

### 2. 데이터 소스

**옵션 1: 로그인 시 저장된 사용자 정보 사용**
- 로그인 API 응답의 `user.kakao_id`를 로컬 스토리지/상태 관리에 저장
- 마이페이지에서 저장된 값 표시

**옵션 2: 사용자 정보 조회 API 사용**
- `/api/users/me` 엔드포인트에서 사용자 정보 조회
- 응답에 `kakao_id` 포함됨

### 3. 표시 형식 제안

```
카카오 ID: 123456789
```

또는

```
카카오 계정: 123456789
```

또는 아이콘과 함께

```
🔗 카카오 ID: 123456789
```

### 4. 상태 관리 확인

로그인 시 사용자 정보를 저장하는 부분을 확인하고, `kakao_id`도 함께 저장되도록 해주세요.

**예시 (React/TypeScript)**:
```typescript
// 로그인 응답 처리
interface LoginResponse {
  token: {
    access: string;
    refresh: string;
  };
  user: {
    id: number;
    kakao_id: number;  // ✅ 이 필드 사용
    nickname: string;
    profile_image_url: string;
  };
  is_new: boolean;
}

// 사용자 정보 저장
const handleLogin = async (response: LoginResponse) => {
  // 토큰 저장
  localStorage.setItem('accessToken', response.token.access);
  localStorage.setItem('refreshToken', response.token.refresh);
  
  // 사용자 정보 저장 (kakao_id 포함)
  setUser({
    id: response.user.id,
    kakao_id: response.user.kakao_id,  // ✅ 추가
    nickname: response.user.nickname,
    profile_image_url: response.user.profile_image_url,
  });
};
```

### 5. 마이페이지 컴포넌트 수정

```tsx
// 마이페이지 계정정보 섹션 예시
<div className="account-info">
  <div className="login-section">
    {isLoggedIn ? (
      <button onClick={handleLogout}>로그아웃</button>
    ) : (
      <button onClick={handleLogin}>로그인</button>
    )}
  </div>
  
  {/* 카카오 ID 표시 추가 */}
  {isLoggedIn && user?.kakao_id && (
    <div className="kakao-id-display">
      <span>카카오 ID: {user.kakao_id}</span>
    </div>
  )}
</div>
```

## 체크리스트

- [ ] 로그인 API 응답에서 `user.kakao_id` 필드 확인
- [ ] 사용자 정보 저장 시 `kakao_id` 포함 여부 확인
- [ ] 마이페이지 계정정보 섹션에 카카오 ID 표시 UI 추가
- [ ] 로그인 상태일 때만 카카오 ID 표시
- [ ] 스타일링 적용 (디자인 가이드에 맞게)

## 참고사항

- 카카오 ID는 숫자로 표시됩니다 (예: `123456789`)
- 로그인하지 않은 상태에서는 표시하지 않아도 됩니다
- 기존 로그인 로직이 있다면, 사용자 정보 저장 부분만 수정하면 됩니다
- 디자인 팀과 협의하여 적절한 위치와 스타일을 결정해주세요

## 문의사항

구현 중 문제가 발생하거나 추가 정보가 필요하면 백엔드 팀에 문의해주세요.

