# 쿠폰 발급 경로 구분 - issue_key 프론트엔드 가이드

> 쿠폰 API에 `issue_key` 필드가 추가되었습니다. 이를 활용해 쿠폰 발급 경로(앱 방문, 추천, 일괄 발급 등)를 구분할 수 있습니다.

---

## 1. 변경 요약

| 구분 | 기존 | 변경 후 |
|------|------|---------|
| 쿠폰 목록 API | `issue_key` 없음 | `issue_key` 필드 추가 |
| 쿠폰 확인 API (PIN 입력) | `issue_key` 없음 | `issue_key` 필드 추가 |
| 발급 경로 구분 | `coupon_type_code`만으로는 앱 방문/일괄 발급 구분 불가 | `issue_key` prefix로 명확히 구분 가능 |

---

## 2. API 변경 사항

### 2.1 내 쿠폰 목록 - `GET /api/coupons/my/`

**추가된 필드:**
```json
{
  "code": "ABC123",
  "status": "ISSUED",
  "coupon_type": 1,
  "coupon_type_code": "WELCOME_3000",
  "coupon_type_title": "5개 보상",
  "campaign": 1,
  "restaurant_id": 101,
  "restaurant_name": "OO식당",
  "benefit": { ... },
  "issue_key": "APP_OPEN:123:20250227:101"
}
```

### 2.2 쿠폰 확인 - `POST /api/coupons/check/`

**요청:** `{"coupon_code": "ABC123"}`

**추가된 필드:**
```json
{
  "code": "ABC123",
  "status": "ISSUED",
  "coupon_type": 1,
  "restaurant_id": 101,
  "restaurant_name": "OO식당",
  "benefit": { ... },
  "issue_key": "APP_OPEN:123:20250227:101"
}
```

---

## 3. issue_key prefix별 발급 경로

| prefix | 발급 경로 | 설명 |
|--------|-----------|------|
| `APP_OPEN:` | 앱 방문 | 앱 접속(로그인/토큰 갱신) 시 발급 |
| `AMBASSADOR:` | 일괄 발급 | 엠버서더 보상 등 명령어로 일괄 발급 |
| `REFERRAL_REFERRER:` | 추천인 | 친구 초대한 사람에게 발급 |
| `REFERRAL_REFEREE:` | 피추천인 | 초대받은 사람에게 발급 |
| `EVENT_REWARD:` | 이벤트 추천 | 운영진 이벤트 추천코드로 발급 |
| `SIGNUP:` | 신규가입 | 회원가입 완료 시 발급 |
| `STAMP_REWARD:` | 스탬프 보상 | 스탬프 적립 달성 시 발급 |
| `FLASH:` | 플래시 | 플래시 드롭 이벤트 발급 |
| `FINAL_EXAM:` | 기말고사 | 기말고사 이벤트 발급 |
| `null` 또는 기타 | 기타 | 위 패턴에 해당하지 않는 쿠폰 |

---

## 4. 프론트엔드 활용 예시

### 4.1 발급 경로 판별 유틸 함수

```javascript
/**
 * issue_key prefix로 쿠폰 발급 경로 반환
 * @param {string|null} issueKey - API 응답의 issue_key
 * @returns {string} 발급 경로 식별자
 */
function getIssuanceSource(issueKey) {
  if (!issueKey) return 'unknown';
  if (issueKey.startsWith('APP_OPEN:')) return 'app_open';           // 앱 방문
  if (issueKey.startsWith('AMBASSADOR:')) return 'bulk';              // 일괄 발급
  if (issueKey.startsWith('REFERRAL_REFERRER:')) return 'referrer';   // 추천인
  if (issueKey.startsWith('REFERRAL_REFEREE:')) return 'referee';     // 피추천인
  if (issueKey.startsWith('EVENT_REWARD:')) return 'event_referral';  // 이벤트 추천
  if (issueKey.startsWith('SIGNUP:')) return 'signup';                // 신규가입
  if (issueKey.startsWith('STAMP_REWARD:')) return 'stamp';           // 스탬프 보상
  if (issueKey.startsWith('FLASH:')) return 'flash';                  // 플래시
  if (issueKey.startsWith('FINAL_EXAM:')) return 'final_exam';        // 기말고사
  return 'other';
}
```

### 4.2 쿠폰 사용 시 UI 분기 예시

```javascript
// 쿠폰 사용 확인 팝업에서 발급 경로별 안내 문구 표시
const source = getIssuanceSource(coupon.issue_key);

if (source === 'app_open') {
  // 앱 방문 쿠폰 전용 안내
} else if (source === 'referrer' || source === 'referee') {
  // 추천 보상 쿠폰 전용 안내
} else if (source === 'bulk') {
  // 엠버서더/일괄 발급 쿠폰 전용 안내
} else if (source === 'stamp') {
  // 스탬프 보상 쿠폰 전용 안내
}
```

### 4.3 쿠폰 목록에서 아이콘/배지 표시

```javascript
// 쿠폰 카드에 발급 경로별 아이콘 표시
const getCouponBadge = (coupon) => {
  const source = getIssuanceSource(coupon.issue_key);
  const badges = {
    app_open: '앱 방문',
    referrer: '친구 초대',
    referee: '신규 가입',
    bulk: '특별',
    stamp: '스탬프',
    flash: '플래시',
  };
  return badges[source] || null;
};
```

---

## 5. 주의사항

- `issue_key`는 `null` 또는 빈 문자열일 수 있습니다. (기존 데이터 또는 일부 발급 경로)
- prefix는 `:`로 구분되며, 대소문자를 구분합니다.
- `coupon_type_code`와 함께 사용하면 더 정확한 분기가 가능합니다. (예: `WELCOME_3000` + `APP_OPEN:` = 앱 방문 웰컴 쿠폰)

---

## 6. 변경 적용 일시

- 백엔드 적용: 2025-02-27
- 프론트엔드 대응: 협의 후 적용
