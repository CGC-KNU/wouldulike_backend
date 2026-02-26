"""
식당별 스탬프 보상 규칙·쿠폰 내용 조회·설정·수정·삭제.

사용 예:
  # 목록 조회 (전체 또는 식당 지정)
  python manage.py stamp_reward_rule list
  python manage.py stamp_reward_rule list 101

  # THRESHOLD 규칙 + 쿠폰 내용 한 번에 설정 (notes: 사용 가능 조건)
  python manage.py stamp_reward_rule set 101 --type THRESHOLD --stamps 1,3,5,7,10 \\
    --benefits '{"1":{"title":"1개 보상","subtitle":"3,000원 할인","value":3000,"notes":"최소 주문 1만원"},"5":{"title":"5개 보상","subtitle":"5,000원 할인","value":5000,"notes":"음료만 사용 가능"}}'

  # THRESHOLD: 1, 5, 10개 + 쿠폰 내용
  python manage.py stamp_reward_rule set 102 --type THRESHOLD --stamps 1,5,10 \\
    --benefits '{"1":{"title":"1개","subtitle":"3천원","value":3000},"5":{"title":"5개","subtitle":"5천원","value":5000},"10":{"title":"10개","subtitle":"1만원","value":10000}}'

  # VISIT 규칙 + 쿠폰 내용
  python manage.py stamp_reward_rule set 103 --type VISIT \\
    --benefits '{"1_4":{"title":"1~4회 보상","subtitle":"3,000원","value":3000},"5_9":{"title":"5~9회 보상","subtitle":"5,000원","value":5000},"10":{"title":"10회 보상","subtitle":"10,000원","value":10000}}'

  # 규칙 삭제 (쿠폰 혜택은 유지)
  python manage.py stamp_reward_rule delete 101

  # 규칙+쿠폰혜택 모두 삭제
  python manage.py stamp_reward_rule delete 101 --remove-benefits
"""
import json
from django.core.management.base import BaseCommand
from django.db import connections, router

from coupons.models import StampRewardRule, CouponType, RestaurantCouponBenefit
from restaurants.models import AffiliateRestaurant
from coupons.service import STAMP_DB_ALIAS

# 스탬프 개수 → 쿠폰 타입 코드 기본 매핑
DEFAULT_THRESHOLD_COUPONS = {
    1: "STAMP_REWARD_1",
    3: "STAMP_REWARD_3",
    5: "STAMP_REWARD_5",
    7: "STAMP_REWARD_7",
    10: "STAMP_REWARD_10",
}

# VISIT 패턴 기본 config
DEFAULT_VISIT_CONFIG = {
    "ranges": [
        {"min_visit": 1, "max_visit": 4, "coupon_type_code": "STAMP_VISIT_1_4"},
        {"min_visit": 5, "max_visit": 9, "coupon_type_code": "STAMP_VISIT_5_9"},
        {"min_visit": 10, "max_visit": 10, "coupon_type_code": "STAMP_VISIT_10"},
    ],
    "cycle_target": 10,
}

# VISIT 구간 → 쿠폰 타입 코드
VISIT_RANGE_TO_COUPON = {
    "1_4": "STAMP_VISIT_1_4",
    "5_9": "STAMP_VISIT_5_9",
    "10": "STAMP_VISIT_10",
}


def get_restaurant_name(restaurant_id: int) -> str:
    """restaurant_id로 식당명 조회."""
    try:
        with connections[STAMP_DB_ALIAS].cursor() as cursor:
            cursor.execute(
                "SELECT name FROM restaurants_affiliate WHERE restaurant_id = %s",
                [restaurant_id],
            )
            row = cursor.fetchone()
            return row[0] if row else "-"
    except Exception:
        return "-"


class Command(BaseCommand):
    help = "식당별 스탬프 보상 규칙 조회·설정·수정·삭제"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action", required=True)

        # list
        list_parser = subparsers.add_parser("list", help="규칙 목록 조회")
        list_parser.add_argument(
            "restaurant_id",
            type=int,
            nargs="?",
            default=None,
            help="식당 ID (생략 시 전체)",
        )

        # set
        set_parser = subparsers.add_parser("set", help="규칙 설정/수정")
        set_parser.add_argument("restaurant_id", type=int)
        set_parser.add_argument("--type", choices=["THRESHOLD", "VISIT"], required=True)
        set_parser.add_argument(
            "--stamps",
            type=str,
            help="THRESHOLD용: 발급 시점 (쉼표 구분). 예: 1,3,5,7,10",
        )
        set_parser.add_argument(
            "--config",
            type=str,
            help="전체 config JSON (--stamps 대신 상세 지정 시)",
        )
        set_parser.add_argument(
            "--cycle",
            type=int,
            default=10,
            help="사이클 목표 (기본 10)",
        )
        set_parser.add_argument(
            "--benefits",
            type=str,
            help='스탬프별 쿠폰 내용 JSON. 값에 notes(비고/사용조건) 포함 가능. 예: {"title":"...","subtitle":"...","value":3000,"notes":"최소 주문 1만원"}',
        )
        set_parser.add_argument("--inactive", action="store_true", help="비활성화")

        # delete
        delete_parser = subparsers.add_parser("delete", help="규칙 삭제")
        delete_parser.add_argument("restaurant_id", type=int)
        delete_parser.add_argument(
            "--yes",
            action="store_true",
            help="확인 없이 삭제",
        )
        delete_parser.add_argument(
            "--remove-benefits",
            action="store_true",
            help="해당 식당의 스탬프 쿠폰 혜택(RestaurantCouponBenefit)도 함께 삭제",
        )

    def handle(self, *args, **options):
        action = options["action"]
        if action == "list":
            self._list(options.get("restaurant_id"))
        elif action == "set":
            self._set(options)
        elif action == "delete":
            self._delete(
                options["restaurant_id"],
                options.get("yes", False),
                options.get("remove_benefits", False),
            )

    def _list(self, restaurant_id: int | None):
        qs = StampRewardRule.objects.using(STAMP_DB_ALIAS).order_by("restaurant_id")
        if restaurant_id is not None:
            qs = qs.filter(restaurant_id=restaurant_id)

        rules = list(qs)
        if not rules:
            self.stdout.write("등록된 규칙이 없습니다.")
            return

        alias = router.db_for_read(RestaurantCouponBenefit)
        stamp_coupon_codes = set(DEFAULT_THRESHOLD_COUPONS.values()) | set(VISIT_RANGE_TO_COUPON.values())

        for r in rules:
            name = get_restaurant_name(r.restaurant_id)
            status = "활성" if r.active else "비활성"
            self.stdout.write(f"\n[{r.restaurant_id}] {name} ({status})")
            self.stdout.write(f"  타입: {r.rule_type}")
            self.stdout.write(f"  설정: {json.dumps(r.config_json, ensure_ascii=False)}")

            benefits = RestaurantCouponBenefit.objects.using(alias).filter(
                restaurant_id=r.restaurant_id,
                coupon_type__code__in=stamp_coupon_codes,
                active=True,
            ).select_related("coupon_type")
            if benefits:
                self.stdout.write("  쿠폰 혜택:")
                for b in benefits:
                    val = b.benefit_json.get("value", "-") if b.benefit_json else "-"
                    notes = f" | {b.notes}" if b.notes else ""
                    self.stdout.write(f"    - {b.coupon_type.code}: {b.title} / {b.subtitle} / {val}원{notes}")

    def _set(self, options: dict):
        rid = options["restaurant_id"]
        rule_type = options["type"]
        inactive = options.get("inactive", False)

        if options.get("config"):
            config = json.loads(options["config"])
        elif rule_type == "THRESHOLD":
            stamps_raw = options.get("stamps")
            if not stamps_raw:
                self.stderr.write(self.style.ERROR("--stamps 또는 --config 필요"))
                return
            stamps = [int(s.strip()) for s in stamps_raw.split(",") if s.strip()]
            if not stamps:
                self.stderr.write(self.style.ERROR("--stamps에 유효한 숫자를 입력하세요"))
                return
            cycle = options.get("cycle", 10)
            thresholds = []
            for s in sorted(stamps):
                code = DEFAULT_THRESHOLD_COUPONS.get(s)
                if not code:
                    self.stderr.write(
                        self.style.WARNING(f"스탬프 {s}개용 기본 쿠폰 없음. STAMP_REWARD_{s} 사용")
                    )
                    code = f"STAMP_REWARD_{s}"
                thresholds.append({"stamps": s, "coupon_type_code": code})
            config = {"thresholds": thresholds, "cycle_target": cycle}
        else:
            config = dict(DEFAULT_VISIT_CONFIG)
            config["cycle_target"] = options.get("cycle", 10)

        rule, created = StampRewardRule.objects.using(STAMP_DB_ALIAS).update_or_create(
            restaurant_id=rid,
            defaults={
                "rule_type": rule_type,
                "config_json": config,
                "active": not inactive,
            },
        )
        action = "생성" if created else "수정"
        name = get_restaurant_name(rid)
        self.stdout.write(
            self.style.SUCCESS(f"{action} 완료: [{rid}] {name} ({rule_type})")
        )
        self.stdout.write(f"  설정: {json.dumps(config, ensure_ascii=False)}")

        # 쿠폰 혜택(제목/부제목/금액) 설정
        benefits_raw = options.get("benefits")
        if benefits_raw:
            self._apply_benefits(rid, rule_type, config, json.loads(benefits_raw))

    def _apply_benefits(
        self, restaurant_id: int, rule_type: str, config: dict, benefits: dict
    ) -> None:
        """스탬프별 쿠폰 혜택(RestaurantCouponBenefit) 생성/수정."""
        alias = router.db_for_write(RestaurantCouponBenefit)

        # 식당 존재 확인
        try:
            AffiliateRestaurant.objects.using(alias).get(restaurant_id=restaurant_id)
        except AffiliateRestaurant.DoesNotExist:
            self.stderr.write(
                self.style.WARNING(f"제휴 식당 없음: {restaurant_id}. 쿠폰 혜택 건너뜀.")
            )
            return

        coupon_map: dict[str, str] = {}  # benefits 키 → coupon_type_code
        if rule_type == "THRESHOLD":
            for t in config.get("thresholds", []):
                coupon_map[str(t["stamps"])] = t["coupon_type_code"]
        else:
            for r in config.get("ranges", []):
                min_v, max_v = r.get("min_visit"), r.get("max_visit")
                code = r.get("coupon_type_code")
                if min_v is not None and max_v is not None and code:
                    key = f"{min_v}_{max_v}" if min_v != max_v else str(min_v)
                    coupon_map[key] = code
            if not coupon_map:
                coupon_map = dict(VISIT_RANGE_TO_COUPON)

        count = 0
        for key, data in benefits.items():
            if not isinstance(data, dict):
                continue
            coupon_type_code = coupon_map.get(key)
            if not coupon_type_code:
                self.stderr.write(self.style.WARNING(f"알 수 없는 키 '{key}' 건너뜀"))
                continue

            title = (data.get("title") or "").strip() or coupon_type_code
            subtitle = (data.get("subtitle") or "").strip()
            notes = (data.get("notes") or "").strip()
            if "benefit" in data:
                benefit_json = data["benefit"]
            elif "value" in data:
                benefit_json = {"type": "fixed", "value": int(data["value"])}
            else:
                benefit_json = {}

            try:
                ct = CouponType.objects.using(alias).get(code=coupon_type_code)
            except CouponType.DoesNotExist:
                self.stderr.write(
                    self.style.WARNING(f"CouponType '{coupon_type_code}' 없음. 건너뜀")
                )
                continue

            RestaurantCouponBenefit.objects.using(alias).update_or_create(
                coupon_type=ct,
                restaurant_id=restaurant_id,
                defaults={
                    "title": title,
                    "subtitle": subtitle,
                    "benefit_json": benefit_json,
                    "notes": notes,
                    "active": True,
                },
            )
            count += 1
            self.stdout.write(f"  쿠폰 혜택 설정: {coupon_type_code} - {title}")

        if count:
            self.stdout.write(self.style.SUCCESS(f"  쿠폰 혜택 {count}건 적용 완료"))

    def _delete(self, restaurant_id: int, yes: bool, remove_benefits: bool):
        try:
            rule = StampRewardRule.objects.using(STAMP_DB_ALIAS).get(restaurant_id=restaurant_id)
        except StampRewardRule.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"규칙 없음: restaurant_id={restaurant_id}"))
            return

        name = get_restaurant_name(restaurant_id)
        if not yes:
            msg = f"[{restaurant_id}] {name} 규칙을 삭제할까요?"
            if remove_benefits:
                msg += " (스탬프 쿠폰 혜택도 함께 삭제됩니다)"
            msg += " (y/N): "
            confirm = input(msg)
            if confirm.lower() != "y":
                self.stdout.write("취소됨")
                return

        if remove_benefits:
            alias = router.db_for_write(RestaurantCouponBenefit)
            stamp_codes = set(DEFAULT_THRESHOLD_COUPONS.values()) | set(
                VISIT_RANGE_TO_COUPON.values()
            )
            deleted, _ = RestaurantCouponBenefit.objects.using(alias).filter(
                restaurant_id=restaurant_id,
                coupon_type__code__in=stamp_codes,
            ).delete()
            self.stdout.write(self.style.SUCCESS(f"  스탬프 쿠폰 혜택 {deleted}건 삭제"))

        rule.delete()
        self.stdout.write(self.style.SUCCESS(f"삭제 완료: [{restaurant_id}] {name}"))
