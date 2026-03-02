"""
CSV 기반 식당별 스탬프 보상 규칙(StampRewardRule) 및 쿠폰 혜택(RestaurantCouponBenefit)을 DB에 적용합니다.

26-1 우주라이크 제휴 식당 CSV 내용을 반영합니다.
- 프리미엄: 1, 2, 3, 5, 7, 10개 스탬프 (정든밤은 VISIT 패턴)
- 일반: 1, 3, 5, 6, 7, 9, 10개 스탬프
- 제외: Better, 와비사비, 고니식탁 (포차1번지먹새통은 스탬프만 포함)
"""
from django.core.management.base import BaseCommand
from django.db import router

from coupons.models import StampRewardRule, CouponType, RestaurantCouponBenefit
from coupons.service import STAMP_DB_ALIAS

# 식당별 스탬프 규칙 및 혜택 (CSV 기반 정리)
# THRESHOLD: {stamps: [(개수, title, notes), ...], notes: 식당 스탬프 비고 (프론트 식당 상세 표기용)}
# VISIT: {ranges: [(min, max, title, notes), ...], notes: 식당 스탬프 비고}
STAMP_DATA = {
    # ---- 프리미엄 ----
    97: {  # 정든밤 - VISIT 패턴
        "rule_type": "VISIT",
        "config": {
            "ranges": [
                (1, 4, "감자튀김 제공", ""),
                (5, 9, "사이드메뉴 제공", ""),
                (10, 10, "메인메뉴 제공", ""),
            ],
            "cycle_target": 10,
            "notes": "",
        },
    },
    33: {  # 구구포차 본점
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (1, "생맥주 500CC / 하이볼", "8인 이하 방문시, 중복 이벤트 불가"),
                (3, "치킨/통닭 랜덤 한마리 (17-19시)", ""),
                (5, "치킨/통닭 랜덤 한마리 (17-19시)", ""),
                (7, "치킨/통닭 랜덤 한마리 (17-19시)", ""),
                (10, "치킨/통닭 랜덤 한마리 (17-19시)", "8인 이하 방문시, 중복 이벤트 불가"),
            ],
            "cycle_target": 10,
            "notes": "8인 이하 방문시, 중복 이벤트 불가",
        },
    },
    145: {  # 통통주먹구이
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "음료 서비스", "3만원 이상 주문시, 5인 이하"),
                (5, "껍데기 1인분", ""),
                (7, "육회 빙수 1접시", ""),
                (10, "주먹 통구이 3인분", "3만원 이상 주문시, 5인 이하"),
            ],
            "cycle_target": 10,
            "notes": "3만원 이상 주문시, 5인 이하",
        },
    },
    143: {  # 스톡홀롬샐러드
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "훈제란 제공", "샐러드 5,000원 이상 결제시"),
                (5, "아메리카노 교환권", ""),
                (7, "훈제란 제공", ""),
                (10, "50% 할인 (최대 5,000원)", "샐러드 5,000원 이상 결제시"),
            ],
            "cycle_target": 10,
            "notes": "샐러드 5,000원 이상 결제시",
        },
    },
    19: {  # 벨로
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (1, "음료 서비스", "20,000원 이상 결제시, 2인 이상"),
                (5, "20% 할인", ""),
                (10, "20% 할인", "20,000원 이상 결제시"),
            ],
            "cycle_target": 10,
            "notes": "20,000원 이상 결제시, 2인 이상",
        },
    },
    146: {  # 닭동가리
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (5, "사이드메뉴", "21,000원 이상 결제시, 8인 이하"),
                (10, "치킨 한마리", "21,000원 이상 결제시, 8인 이하"),
            ],
            "cycle_target": 10,
            "notes": "21,000원 이상 결제시, 8인 이하",
        },
    },
    62: {  # 마름모식당
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (5, "작은냉우동 1개", "최소 1만원 이상 결제 시 적립, 테이블당 최대 2개 적립 가능"),
                (10, "마름모냉우동 or 들기름 우동", ""),
            ],
            "cycle_target": 10,
            "notes": "최소 1만원 이상 결제 시 적립, 테이블당 최대 2개 적립 가능",
        },
    },
    144: {  # 주비 두루 향기롭다
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "우유푸딩", "결제당 1회 적립"),
                (5, "초콜릿 케이크 / 바나나 브레드", ""),
                (7, "아메리카노", ""),
                (10, "전 음료 메뉴 택 1", ""),
            ],
            "cycle_target": 10,
            "notes": "결제당 1회 적립",
        },
    },
    266: {  # 북성로우동불고기
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (1, "사이드메뉴 택 1", "결제시, 메인메뉴 주문시 (쿠폰 처리)"),
                (3, "사이드메뉴 택 1", ""),
                (5, "오뎅탕 or 치킨 가라아게", ""),
                (7, "오뎅탕 or 치킨 가라아게", ""),
                (10, "메인메뉴 택 1", ""),
            ],
            "cycle_target": 10,
            "notes": "결제시, 메인메뉴 주문시 (쿠폰 처리)",
        },
    },
    285: {  # 난탄
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (1, "음료 제공", "방문시"),
                (2, "아이스크림", ""),
                (3, "눈사람 요거트 샤베트 or 망고 요거트 아이스크림", ""),
                (5, "사이드 택 1", ""),
                (7, "메인메뉴 택 1", ""),
                (10, "연태고량주 대", ""),
            ],
            "cycle_target": 10,
            "notes": "방문시",
        },
    },
    147: {  # 포차1번지먹새통 경북대점
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (1, "음료 1개", ""),
                (3, "슬러시 황도 1개", ""),
                (5, "프리미엄 제외 메뉴 1개", ""),
                (7, "프리미엄 제외 메뉴 1개 + 주류 1병", ""),
                (10, "전 메뉴 중 1개", ""),
            ],
            "cycle_target": 10,
            "notes": "테이블 당 1회\n단체 제외 (8인 이하)\n주류 주문 필수\n서비스 메뉴 단독 주문 불가 (스탬프 10개시 가능)\n마지막 적립일 기준 2개월 내 사용 가능",
        },
    },
    # ---- 일반 ----
    74: {  # 한끼갈비
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "납작만두 증정", ""),
            ],
            "cycle_target": 3,
            "notes": "",
        },
    },
    47: {  # 대부 대왕유부초밥
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (5, "교자만두", ""),
                (10, "새우튀김 샐러드", ""),
            ],
            "cycle_target": 10,
            "notes": "",
        },
    },
    41: {  # 부리또익스프레스
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (7, "치킨 부리또 1개", ""),
            ],
            "cycle_target": 7,
            "notes": "",
        },
    },
    56: {  # 다이와스시
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "타코야끼 10개", ""),
                (10, "만원 할인", ""),
            ],
            "cycle_target": 10,
            "notes": "",
        },
    },
    249: {  # 고씨네
        "rule_type": "THRESHOLD",
        "config": {
            "thresholds": [
                (3, "고로케 3개", ""),
                (7, "닭튀김 4개", ""),
                (10, "돈가스", ""),
            ],
            "cycle_target": 10,
            "notes": "",
        },
    },
}

# VISIT 패턴 쿠폰 타입
VISIT_COUPON_TYPES = {
    "1_4": "STAMP_VISIT_1_4",
    "5_9": "STAMP_VISIT_5_9",
    "10": "STAMP_VISIT_10",
}

# THRESHOLD 스탬프 개수 → 쿠폰 타입
THRESHOLD_COUPON_TYPES = {
    n: f"STAMP_REWARD_{n}" for n in [1, 2, 3, 5, 6, 7, 9, 10]
}

# cloudsql에 없을 수 있는 CouponType (마이그레이션 0027)
EXTRA_STAMP_COUPON_SPECS = [
    {"code": "STAMP_REWARD_2", "defaults": {"title": "Stamp Reward (2)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
    {"code": "STAMP_REWARD_6", "defaults": {"title": "Stamp Reward (6)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
    {"code": "STAMP_REWARD_9", "defaults": {"title": "Stamp Reward (9)", "benefit_json": {"type": "fixed", "value": 3000}, "valid_days": 14, "per_user_limit": 999}},
]


class Command(BaseCommand):
    help = "CSV 기반 스탬프 보상 규칙 및 쿠폰 혜택을 DB에 적용"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 출력만",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY-RUN 모드 (저장하지 않음)"))

        benefit_alias = router.db_for_write(RestaurantCouponBenefit)
        # STAMP_REWARD_2, 6, 9 CouponType이 없으면 생성 (cloudsql)
        if not dry_run:
            for spec in EXTRA_STAMP_COUPON_SPECS:
                CouponType.objects.using(benefit_alias).get_or_create(
                    code=spec["code"], defaults=spec["defaults"]
                )

        rule_alias = STAMP_DB_ALIAS

        rules_created = rules_updated = 0
        benefits_created = benefits_updated = 0

        for restaurant_id, data in STAMP_DATA.items():
            rule_type = data["rule_type"]
            config = data["config"]

            # StampRewardRule config_json 구성
            stamp_notes = config.get("notes", "")
            if rule_type == "VISIT":
                range_keys = [
                    f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
                    for min_v, max_v, _, _ in config["ranges"]
                ]
                config_json = {
                    "ranges": [
                        {
                            "min_visit": config["ranges"][i][0],
                            "max_visit": config["ranges"][i][1],
                            "coupon_type_code": VISIT_COUPON_TYPES[range_keys[i]],
                        }
                        for i in range(len(config["ranges"]))
                    ],
                    "cycle_target": config.get("cycle_target", 10),
                    "notes": stamp_notes,
                }
            else:
                config_json = {
                    "thresholds": [
                        {
                            "stamps": t[0],
                            "coupon_type_code": THRESHOLD_COUPON_TYPES[t[0]],
                        }
                        for t in config["thresholds"]
                    ],
                    "cycle_target": config.get("cycle_target", 10),
                    "notes": stamp_notes,
                }

            # StampRewardRule 저장
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] StampRewardRule {restaurant_id}: {rule_type} "
                    f"{config_json}"
                )
                rules_created += 1
            else:
                rule, created = StampRewardRule.objects.using(rule_alias).update_or_create(
                    restaurant_id=restaurant_id,
                    defaults={
                        "rule_type": rule_type,
                        "config_json": config_json,
                        "active": True,
                    },
                )
                if created:
                    rules_created += 1
                else:
                    rules_updated += 1

            # RestaurantCouponBenefit 저장
            try:
                ct_qs = CouponType.objects.using(benefit_alias)
                if rule_type == "VISIT":
                    for i, (min_v, max_v, title, notes) in enumerate(config["ranges"]):
                        key = f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
                        code = VISIT_COUPON_TYPES[key]
                        try:
                            ct = ct_qs.get(code=code)
                        except CouponType.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f"CouponType {code} 없음, 건너뜀")
                            )
                            continue
                        if dry_run:
                            self.stdout.write(
                                f"  [DRY-RUN] Benefit {code}: {title} | {notes}"
                            )
                            benefits_created += 1
                        else:
                            _, created = RestaurantCouponBenefit.objects.using(
                                benefit_alias
                            ).update_or_create(
                                coupon_type=ct,
                                restaurant_id=restaurant_id,
                                sort_order=0,
                                defaults={
                                    "title": title[:120],
                                    "subtitle": "",
                                    "notes": notes[:500] if notes else "",
                                    "benefit_json": {},
                                    "active": True,
                                },
                            )
                            if created:
                                benefits_created += 1
                            else:
                                benefits_updated += 1
                else:
                    for stamps, title, notes in config["thresholds"]:
                        code = THRESHOLD_COUPON_TYPES[stamps]
                        try:
                            ct = ct_qs.get(code=code)
                        except CouponType.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f"CouponType {code} 없음, 건너뜀")
                            )
                            continue
                        if dry_run:
                            self.stdout.write(
                                f"  [DRY-RUN] Benefit {code} ({stamps}개): {title} | {notes}"
                            )
                            benefits_created += 1
                        else:
                            _, created = RestaurantCouponBenefit.objects.using(
                                benefit_alias
                            ).update_or_create(
                                coupon_type=ct,
                                restaurant_id=restaurant_id,
                                sort_order=0,
                                defaults={
                                    "title": title[:120],
                                    "subtitle": "",
                                    "notes": notes[:500] if notes else "",
                                    "benefit_json": {},
                                    "active": True,
                                },
                            )
                            if created:
                                benefits_created += 1
                            else:
                                benefits_updated += 1
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"restaurant_id={restaurant_id} 오류: {e}")
                )
                raise

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: StampRewardRule 생성 {rules_created}개, 수정 {rules_updated}개 | "
                f"RestaurantCouponBenefit 생성 {benefits_created}개, 수정 {benefits_updated}개 "
                f"(dry_run={dry_run})"
            )
        )
