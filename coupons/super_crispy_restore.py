"""
슈퍼크리스피 경북대점(restaurant_id=298) 제휴 복구.

정든밤 축제 주막이 298을 잠시 사용한 뒤 299로 이전하면서
- restaurants_affiliate: is_affiliate=FALSE, 이름·PIN 등이 축제 값으로 덮였을 수 있음
- RestaurantCouponBenefit: restaurant_id=298 행은 active=FALSE, 일부는 299로 이전됨
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from django.db import connections, router
from django.utils import timezone

RESTAURANT_ID = 298
RESTAURANT_NAME = "슈퍼크리스피 경북대점"
# Koyeb/배포 환경 변수 (Git에 값을 넣지 않음)
PIN_ENV_KEYS = ("SUPER_CRISPY_RESTAURANT_PIN", "SUPER_CRISPY_PIN")
DEFAULT_CATEGORY = "양식"
DEFAULT_ZONE = "북문"

# 26-1 우주라이크 제휴 식당 CSV (슈퍼크리스피 경북대점, restaurant_id=298)
CONTRACT = {
    "name": RESTAURANT_NAME,
    "category": "양식",
    "zone": "북문",
    "address": "대구광역시 북구 산격동 1332-10 1층",
    "description": "콰삭한 식감의 치킨버거 맛집",
    "url": "https://naver.me/5b07IxsH",
    "signup_benefits": [
        {"title": "치킨무 공짜", "notes": "치킨 주문시"},
    ],
    "stamp_rewards": {
        3: {"title": "크리스피 핫 윙 1개", "notes": ""},
        5: {"title": "치킨 너겟 3개", "notes": ""},
        7: {"title": "코카콜라 245ml", "notes": ""},
        10: {"title": "햄버거 1+1 (치킨버거 한정)", "notes": ""},
    },
    "stamp_notes": "결제시",
    "naver_alarm_coupon_content": "치킨무 공짜",
}

FESTIVAL_NAME_MARKERS = ("정든밤", "우주라이크 X", "우주라이크X")
FESTIVAL_PIN = "0629"
FESTIVAL_COUPON_CODES = frozenset({"JUNGDUNBAM_FESTIVAL_WED"})
# 축제 주막이 슈퍼크리스피 benefit·스탬프를 잠시 보관하던 ID
FESTIVAL_SLOT_RESTAURANT_ID = 299
FESTIVAL_ADDRESS_MARKERS = ("축제 주막", "80주년")
STAMP_NO_REWARD_MARKER = "스탬프 적립, 보상이 없습니다"

CSV_STAMP_RULE_CONFIG = {
    "thresholds": [
        {"stamps": 3, "coupon_type_code": "STAMP_REWARD_3"},
        {"stamps": 5, "coupon_type_code": "STAMP_REWARD_5"},
        {"stamps": 7, "coupon_type_code": "STAMP_REWARD_7"},
        {"stamps": 10, "coupon_type_code": "STAMP_REWARD_10"},
    ],
    "cycle_target": 10,
    "notes": CONTRACT["stamp_notes"],
}

DEFAULT_STAMP_RULE_CONFIG = CSV_STAMP_RULE_CONFIG


@dataclass
class AffiliateRowSnapshot:
    exists: bool = False
    restaurant_id: int | None = None
    name: str | None = None
    is_affiliate: bool | None = None
    description: str | None = None
    address: str | None = None
    category: str | None = None
    zone: str | None = None
    phone_number: str | None = None
    url: str | None = None
    pin_secret: str | None = None
    s3_image_urls: list | None = None


@dataclass
class RestoreAudit:
    affiliate: AffiliateRowSnapshot = field(default_factory=AffiliateRowSnapshot)
    benefit_rows_at_298: int = 0
    benefit_active_at_298: int = 0
    benefit_inactive_at_298: int = 0
    benefit_rows_at_299: int = 0
    exclusion_rows_at_298: int = 0
    merchant_pin_at_298: str | None = None
    stamp_rule_at_298: bool = False
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def looks_like_festival_row(self) -> bool:
        if not self.affiliate.exists:
            return False
        name = (self.affiliate.name or "").strip()
        if any(m in name for m in FESTIVAL_NAME_MARKERS):
            return True
        if (self.affiliate.pin_secret or "").strip() == FESTIVAL_PIN:
            return True
        desc = (self.affiliate.description or "") or ""
        if "축제 주막" in desc or "80주년" in desc:
            return True
        return False

    def summary_lines(self) -> list[str]:
        lines = [
            f"restaurants_affiliate id={RESTAURANT_ID}: "
            f"exists={self.affiliate.exists} "
            f"name={self.affiliate.name!r} is_affiliate={self.affiliate.is_affiliate}",
            f"benefits@298: total={self.benefit_rows_at_298} "
            f"active={self.benefit_active_at_298} inactive={self.benefit_inactive_at_298}",
            f"benefits@299 (참고): total={self.benefit_rows_at_299}",
            f"exclusions@298: {self.exclusion_rows_at_298}, "
            f"pin@298={self.merchant_pin_at_298!r}, stamp_rule@298={self.stamp_rule_at_298}",
        ]
        if self.looks_like_festival_row():
            lines.append(
                "⚠ 298 행에 축제 주막 흔적(이름·PIN·설명)이 남아 있습니다. 복구 시 슈퍼크리스피 값으로 교정합니다."
            )
        elif self.affiliate.exists and self.affiliate.name and RESTAURANT_NAME not in (
            self.affiliate.name or ""
        ):
            lines.append(
                f"⚠ 이름이 {RESTAURANT_NAME!r} 와 다릅니다: {self.affiliate.name!r}"
            )
        if self.benefit_rows_at_298 == 0:
            lines.append(
                "⚠ 298에 쿠폰 benefit 행이 없습니다. "
                "축제 이전 시 299로 이전됐을 수 있어 import_affiliate_coupon_benefits 등으로 재등록이 필요할 수 있습니다."
            )
        lines.extend(self.warnings)
        lines.extend(self.notes)
        return lines


def _db_alias(db_alias: str | None = None) -> str:
    if db_alias:
        return db_alias
    from coupons.festival_jungdunbam import resolve_cloudsql_alias

    return resolve_cloudsql_alias()


def audit_super_crispy(*, db_alias: str | None = None) -> RestoreAudit:
    alias = _db_alias(db_alias)
    audit = RestoreAudit()

    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            SELECT restaurant_id, name, is_affiliate, description, address,
                   category, zone, phone_number, url, pin_secret, s3_image_urls
            FROM restaurants_affiliate
            WHERE restaurant_id = %s
            """,
            [RESTAURANT_ID],
        )
        row = cursor.fetchone()
        if row:
            audit.affiliate = AffiliateRowSnapshot(
                exists=True,
                restaurant_id=row[0],
                name=row[1],
                is_affiliate=row[2],
                description=row[3],
                address=row[4],
                category=row[5],
                zone=row[6],
                phone_number=row[7],
                url=row[8],
                pin_secret=row[9],
                s3_image_urls=row[10],
            )

        cursor.execute(
            """
            SELECT COUNT(*),
                   COUNT(*) FILTER (WHERE rcb.active IS TRUE),
                   COUNT(*) FILTER (WHERE rcb.active IS NOT TRUE)
            FROM coupons_restaurantcouponbenefit rcb
            WHERE rcb.restaurant_id = %s
            """,
            [RESTAURANT_ID],
        )
        total, active, inactive = cursor.fetchone()
        audit.benefit_rows_at_298 = total or 0
        audit.benefit_active_at_298 = active or 0
        audit.benefit_inactive_at_298 = inactive or 0

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM coupons_restaurantcouponbenefit
            WHERE restaurant_id = 299
            """
        )
        audit.benefit_rows_at_299 = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM coupons_couponrestaurantexclusion
            WHERE restaurant_id = %s
            """,
            [RESTAURANT_ID],
        )
        audit.exclusion_rows_at_298 = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT secret FROM coupons_merchantpin WHERE restaurant_id = %s",
            [RESTAURANT_ID],
        )
        pin_row = cursor.fetchone()
        audit.merchant_pin_at_298 = pin_row[0] if pin_row else None

        cursor.execute(
            """
            SELECT 1 FROM coupons_stamprewardrule
            WHERE restaurant_id = %s AND active IS TRUE
            LIMIT 1
            """,
            [RESTAURANT_ID],
        )
        audit.stamp_rule_at_298 = cursor.fetchone() is not None

    if not audit.affiliate.exists:
        audit.warnings.append("298 restaurants_affiliate 행이 없습니다. 복구 시 새로 INSERT 합니다.")

    return audit


def resolve_super_crispy_pin_from_env() -> str | None:
    """배포 환경 변수에서만 PIN을 읽습니다. 미설정 시 None."""
    for key in PIN_ENV_KEYS:
        raw = (os.environ.get(key) or "").strip()
        if not raw:
            continue
        if not raw.isdigit() or len(raw) < 4:
            raise ValueError(f"{key} must be at least 4 digits")
        return raw
    return None


def apply_super_crispy_pin(
    *,
    db_alias: str | None = None,
    pin: str,
    dry_run: bool = False,
) -> None:
    """MerchantPin + restaurants_affiliate.pin_secret 에 고정 PIN 반영."""
    if not pin.isdigit() or len(pin) < 4:
        raise ValueError("PIN must be at least 4 digits")

    alias = _db_alias(db_alias)
    now = timezone.now()

    if dry_run:
        return

    from coupons.models import MerchantPin

    MerchantPin.objects.using(alias).update_or_create(
        restaurant_id=RESTAURANT_ID,
        defaults={
            "algo": "STATIC",
            "secret": pin,
            "period_sec": 30,
            "last_rotated_at": now,
        },
    )
    with connections[alias].cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurants_affiliate
            SET pin_secret = %s, pin_updated_at = %s
            WHERE restaurant_id = %s
            """,
            [pin, now, RESTAURANT_ID],
        )


def restore_super_crispy_affiliate(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
    reset_pin: bool = False,
    pin: str | None = None,
    recover_merchant_data: bool = True,
) -> RestoreAudit:
    """
    298 슈퍼크리스피 제휴 복구.
    - is_affiliate=TRUE, 이름·카테고리 정리
    - 축제 전용 exclusion 제거, 비축제 benefit 재활성화
    - 축제 스탬프 규칙(298) 비활성화
    - pin 이 주어지면 MerchantPin·affiliate.pin_secret 에 반영 (값은 env/인자로만)
    """
    alias = _db_alias(db_alias)
    audit = audit_super_crispy(db_alias=alias)
    now = timezone.now()

    festival_overwrite = audit.looks_like_festival_row()
    pin_is_festival = (
        (audit.affiliate.pin_secret or "").strip() == FESTIVAL_PIN
        or (audit.merchant_pin_at_298 or "").strip() == FESTIVAL_PIN
    )

    if dry_run:
        audit.notes.append("[DRY-RUN] DB 변경 없음")
        return audit

    with connections[alias].cursor() as cursor:
        if audit.affiliate.exists:
            new_name = RESTAURANT_NAME if festival_overwrite or not audit.affiliate.name else audit.affiliate.name
            if RESTAURANT_NAME not in (new_name or ""):
                new_name = RESTAURANT_NAME

            new_desc = audit.affiliate.description or ""
            if festival_overwrite and (
                "축제" in (new_desc or "") or "80주년" in (new_desc or "")
            ):
                new_desc = ""

            new_category = audit.affiliate.category or DEFAULT_CATEGORY
            if new_category in ("주점", "주막") and festival_overwrite:
                new_category = DEFAULT_CATEGORY

            new_zone = audit.affiliate.zone or DEFAULT_ZONE
            if (new_zone or "").strip() in ("주막",) or festival_overwrite:
                new_zone = DEFAULT_ZONE

            new_address = audit.affiliate.address
            if new_address and any(m in new_address for m in FESTIVAL_ADDRESS_MARKERS):
                new_address = ""

            if reset_pin or pin_is_festival:
                audit.notes.append(
                    "축제 PIN(0629) 감지: 복구 후 pin 인자로 재설정합니다."
                )

            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET name = %s,
                    is_affiliate = TRUE,
                    description = %s,
                    category = %s,
                    zone = %s,
                    address = %s
                WHERE restaurant_id = %s
                """,
                [new_name, new_desc, new_category, new_zone, new_address, RESTAURANT_ID],
            )
        else:
            cursor.execute(
                """
                INSERT INTO restaurants_affiliate (
                    restaurant_id, name, is_affiliate, description,
                    category, zone, s3_image_urls
                ) VALUES (%s, %s, TRUE, %s, %s, %s, %s)
                """,
                [RESTAURANT_ID, RESTAURANT_NAME, "", DEFAULT_CATEGORY, DEFAULT_ZONE, []],
            )
            audit.notes.append("298 행을 신규 INSERT 했습니다.")

        # 축제·기타 발급 차단 exclusion 제거 (298은 일반 제휴로 복귀)
        cursor.execute(
            """
            DELETE FROM coupons_couponrestaurantexclusion
            WHERE restaurant_id = %s
              AND coupon_type_id IN (
                SELECT id FROM coupons_coupontype WHERE code = ANY(%s)
              )
            """,
            [RESTAURANT_ID, list(FESTIVAL_COUPON_CODES)],
        )

        # 298에 남은 비축제 benefit 재활성화
        cursor.execute(
            """
            UPDATE coupons_restaurantcouponbenefit rcb
            SET active = TRUE
            FROM coupons_coupontype ct
            WHERE rcb.coupon_type_id = ct.id
              AND rcb.restaurant_id = %s
              AND ct.code <> ALL(%s)
              AND rcb.active IS NOT TRUE
            """,
            [RESTAURANT_ID, list(FESTIVAL_COUPON_CODES)],
        )
        reactivated = cursor.rowcount
        if reactivated:
            audit.notes.append(f"298 benefit {reactivated}건 active=TRUE 로 복구")

        if reset_pin or pin_is_festival:
            cursor.execute(
                "DELETE FROM coupons_merchantpin WHERE restaurant_id = %s",
                [RESTAURANT_ID],
            )

    if pin:
        apply_super_crispy_pin(db_alias=alias, pin=pin, dry_run=False)
        audit.notes.append("PIN 설정 완료 (MerchantPin·affiliate)")

    if recover_merchant_data:
        merchant_audit = recover_super_crispy_merchant_data(
            db_alias=alias, dry_run=False
        )
        audit.notes.extend(merchant_audit.notes)

    audit.notes.append("복구 완료: is_affiliate=TRUE")
    return audit_super_crispy(db_alias=alias)


def apply_super_crispy_pin_from_env(*, db_alias: str | None = None) -> bool:
    """SUPER_CRISPY_RESTAURANT_PIN 이 있으면 298 PIN 반영. 없으면 False."""
    pin = resolve_super_crispy_pin_from_env()
    if not pin:
        return False
    apply_super_crispy_pin(db_alias=db_alias, pin=pin)
    return True


def format_audit_report(audit: RestoreAudit) -> str:
    return "\n".join(audit.summary_lines())


def _is_festival_only_benefit(*, coupon_code: str, title: str, subtitle: str, notes: str) -> bool:
    if coupon_code in FESTIVAL_COUPON_CODES:
        return True
    blob = f"{title} {subtitle} {notes}"
    if STAMP_NO_REWARD_MARKER in blob:
        return True
    if any(m in blob for m in FESTIVAL_NAME_MARKERS):
        return True
    return False


def _stamp_rule_config_from_benefits(*, db_alias: str) -> dict | None:
    from coupons.models import RestaurantCouponBenefit

    rows = (
        RestaurantCouponBenefit.objects.using(db_alias)
        .filter(
            restaurant_id=RESTAURANT_ID,
            coupon_type__code__startswith="STAMP_REWARD_",
        )
        .select_related("coupon_type")
        .order_by("coupon_type__code")
    )
    thresholds: list[dict] = []
    for row in rows:
        code = row.coupon_type.code
        suffix = code.removeprefix("STAMP_REWARD_")
        if not suffix.isdigit():
            continue
        thresholds.append({"stamps": int(suffix), "coupon_type_code": code})
    if not thresholds:
        return None
    cycle = max(t["stamps"] for t in thresholds)
    return {"thresholds": thresholds, "cycle_target": cycle}


def _is_stamp_disabled_rule_config(config: dict | None) -> bool:
    if not config:
        return False
    if config.get("stamp_disabled") is True:
        return True
    notes = config.get("notes") or ""
    return STAMP_NO_REWARD_MARKER in notes


def copy_super_crispy_benefits_from_festival_slot(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
) -> int:
    """
    299에 남아 있는(비활성 포함) 슈퍼크리스피 쿠폰 benefit 을 298으로 복사·활성화.
    축제 전용(JUNGDUNBAM_FESTIVAL_WED 등)은 제외.
    """
    alias = _db_alias(db_alias)
    from coupons.models import RestaurantCouponBenefit

    copied = 0
    sources = (
        RestaurantCouponBenefit.objects.using(alias)
        .filter(restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID)
        .select_related("coupon_type")
        .order_by("coupon_type_id", "sort_order", "id")
    )
    for src in sources:
        code = src.coupon_type.code
        if _is_festival_only_benefit(
            coupon_code=code,
            title=src.title or "",
            subtitle=src.subtitle or "",
            notes=src.notes or "",
        ):
            continue
        copied += 1
        if dry_run:
            continue
        RestaurantCouponBenefit.objects.using(alias).update_or_create(
            coupon_type_id=src.coupon_type_id,
            restaurant_id=RESTAURANT_ID,
            sort_order=src.sort_order,
            defaults={
                "title": src.title,
                "subtitle": src.subtitle,
                "notes": src.notes,
                "benefit_json": src.benefit_json or {},
                "active": True,
            },
        )
    return copied


def apply_super_crispy_contract(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
) -> int:
    """CSV 계약 기준 식당 정보·쿠폰·스탬프 benefit 을 298에 반영."""
    alias = _db_alias(db_alias)
    from coupons.models import CouponType, RestaurantCouponBenefit

    updated = 0
    if not dry_run:
        with connections[alias].cursor() as cursor:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET name = %s,
                    category = %s,
                    zone = %s,
                    address = %s,
                    description = %s,
                    url = %s,
                    is_affiliate = TRUE,
                    naver_alarm_coupon_content = %s
                WHERE restaurant_id = %s
                """,
                [
                    CONTRACT["name"],
                    CONTRACT["category"],
                    CONTRACT["zone"],
                    CONTRACT["address"],
                    CONTRACT["description"],
                    CONTRACT["url"],
                    CONTRACT["naver_alarm_coupon_content"],
                    RESTAURANT_ID,
                ],
            )

    signup_codes = ["WELCOME_3000"]
    for idx, item in enumerate(CONTRACT["signup_benefits"]):
        for code in signup_codes:
            try:
                ct = CouponType.objects.using(alias).get(code=code)
            except CouponType.DoesNotExist:
                continue
            updated += 1
            if dry_run:
                continue
            RestaurantCouponBenefit.objects.using(alias).update_or_create(
                coupon_type=ct,
                restaurant_id=RESTAURANT_ID,
                sort_order=idx,
                defaults={
                    "title": item["title"],
                    "subtitle": "",
                    "notes": item["notes"],
                    "benefit_json": {"type": "fixed", "value": 0},
                    "active": True,
                },
            )

    for stamps, item in CONTRACT["stamp_rewards"].items():
        code = f"STAMP_REWARD_{stamps}"
        try:
            ct = CouponType.objects.using(alias).get(code=code)
        except CouponType.DoesNotExist:
            continue
        updated += 1
        if dry_run:
            continue
        RestaurantCouponBenefit.objects.using(alias).update_or_create(
            coupon_type=ct,
            restaurant_id=RESTAURANT_ID,
            sort_order=0,
            defaults={
                "title": item["title"],
                "subtitle": "",
                "notes": item["notes"],
                "benefit_json": {},
                "active": True,
            },
        )

    return updated


def recover_super_crispy_user_accumulation_data(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """
    축제 ID(299)로 이전된 스탬프 지갑·이벤트·쿠폰을 298으로 되돌립니다.
    축제 전용 쿠폰(JUNGDUNBAM_FESTIVAL_WED)은 299에 유지합니다.
    """
    alias = _db_alias(db_alias)
    from coupons.models import Coupon, StampEvent, StampWallet

    stats = {"wallets_moved": 0, "events_moved": 0, "coupons_moved": 0}

    wallet_qs = StampWallet.objects.using(alias).filter(
        restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID
    )
    stats["wallets_at_299"] = wallet_qs.count()
    stats["wallets_with_stamps"] = wallet_qs.filter(stamps__gt=0).count()

    if dry_run:
        stats["events_at_299"] = StampEvent.objects.using(alias).filter(
            restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID
        ).count()
        stats["coupons_at_299"] = Coupon.objects.using(alias).filter(
            restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID
        ).exclude(coupon_type__code__in=FESTIVAL_COUPON_CODES).count()
        return stats

    for wallet in list(wallet_qs):
        existing = (
            StampWallet.objects.using(alias)
            .filter(user_id=wallet.user_id, restaurant_id=RESTAURANT_ID)
            .first()
        )
        if existing:
            existing.stamps = (existing.stamps or 0) + (wallet.stamps or 0)
            existing.save(update_fields=["stamps"])
            StampEvent.objects.using(alias).filter(
                user_id=wallet.user_id,
                restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID,
            ).update(restaurant_id=RESTAURANT_ID)
            wallet.delete()
        else:
            wallet.restaurant_id = RESTAURANT_ID
            wallet.save(update_fields=["restaurant_id"])
        stats["wallets_moved"] += 1

    stats["events_moved"] = StampEvent.objects.using(alias).filter(
        restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID
    ).update(restaurant_id=RESTAURANT_ID)

    stats["coupons_moved"] = (
        Coupon.objects.using(alias)
        .filter(restaurant_id=FESTIVAL_SLOT_RESTAURANT_ID)
        .exclude(coupon_type__code__in=FESTIVAL_COUPON_CODES)
        .update(restaurant_id=RESTAURANT_ID)
    )

    return stats


def verify_super_crispy_against_contract(*, db_alias: str | None = None) -> list[str]:
    """CSV 계약 대비 불일치 목록."""
    alias = _db_alias(db_alias)
    issues: list[str] = []
    audit = audit_super_crispy(db_alias=alias)

    if not audit.affiliate.exists:
        issues.append("298 restaurants_affiliate 행 없음")
        return issues

    aff = audit.affiliate
    if aff.name != CONTRACT["name"]:
        issues.append(f"이름: DB={aff.name!r} 기대={CONTRACT['name']!r}")
    if aff.category != CONTRACT["category"]:
        issues.append(f"카테고리: DB={aff.category!r} 기대={CONTRACT['category']!r}")
    if (aff.zone or "").strip() != CONTRACT["zone"]:
        issues.append(f"구역: DB={aff.zone!r} 기대={CONTRACT['zone']!r}")
    if (aff.address or "").strip() != CONTRACT["address"]:
        issues.append(f"주소: DB={aff.address!r} 기대={CONTRACT['address']!r}")
    if (aff.description or "").strip() != CONTRACT["description"]:
        issues.append(f"설명: DB={aff.description!r} 기대={CONTRACT['description']!r}")
    if (aff.url or "").strip() != CONTRACT["url"]:
        issues.append(f"URL: DB={aff.url!r} 기대={CONTRACT['url']!r}")

    from coupons.models import CouponType, RestaurantCouponBenefit, StampRewardRule
    from coupons.service import STAMP_DB_ALIAS

    for item in CONTRACT["signup_benefits"]:
        row = (
            RestaurantCouponBenefit.objects.using(alias)
            .filter(
                restaurant_id=RESTAURANT_ID,
                coupon_type__code="WELCOME_3000",
                active=True,
            )
            .first()
        )
        if not row:
            issues.append("신규가입 쿠폰 benefit 없음")
        elif (row.title or "").strip() != item["title"]:
            issues.append(f"신규가입 제목: DB={row.title!r} 기대={item['title']!r}")
        elif (row.notes or "").strip() != item["notes"]:
            issues.append(f"신규가입 비고: DB={row.notes!r} 기대={item['notes']!r}")

    for stamps, item in CONTRACT["stamp_rewards"].items():
        code = f"STAMP_REWARD_{stamps}"
        row = (
            RestaurantCouponBenefit.objects.using(alias)
            .filter(
                restaurant_id=RESTAURANT_ID,
                coupon_type__code=code,
                active=True,
            )
            .first()
        )
        if not row:
            issues.append(f"스탬프 {stamps}개 benefit 없음 ({code})")
        elif (row.title or "").strip() != item["title"]:
            issues.append(
                f"스탬프 {stamps}개 제목: DB={row.title!r} 기대={item['title']!r}"
            )

    rule = (
        StampRewardRule.objects.using(STAMP_DB_ALIAS)
        .filter(restaurant_id=RESTAURANT_ID, active=True)
        .first()
    )
    if not rule:
        issues.append("StampRewardRule 없음")
    elif _is_stamp_disabled_rule_config(rule.config_json):
        issues.append("스탬프 규칙이 축제 비활성 설정임")
    else:
        expected_codes = {
            t["coupon_type_code"] for t in CSV_STAMP_RULE_CONFIG["thresholds"]
        }
        actual_codes = {
            t.get("coupon_type_code")
            for t in (rule.config_json or {}).get("thresholds", [])
        }
        if actual_codes != expected_codes:
            issues.append(
                f"스탬프 규칙 코드: DB={sorted(actual_codes)} 기대={sorted(expected_codes)}"
            )
        if (rule.config_json or {}).get("notes", "") != CONTRACT["stamp_notes"]:
            issues.append(
                f"스탬프 비고: DB={(rule.config_json or {}).get('notes')!r} "
                f"기대={CONTRACT['stamp_notes']!r}"
            )

    if audit.benefit_active_at_298 < len(CONTRACT["stamp_rewards"]) + len(
        CONTRACT["signup_benefits"]
    ):
        issues.append(
            f"활성 benefit 수 부족: active={audit.benefit_active_at_298} "
            f"기대 최소 {len(CONTRACT['stamp_rewards']) + len(CONTRACT['signup_benefits'])}"
        )

    pin = audit.merchant_pin_at_298 or (aff.pin_secret if aff else None)
    if not pin:
        issues.append("PIN 미설정 (SUPER_CRISPY_RESTAURANT_PIN 환경 변수 확인)")

    return issues


def restore_super_crispy_stamp_rule(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
) -> bool:
    """298 스탬프 적립 규칙·STAMP_REWARD benefit 활성화 (축제 비활성 설정 제거)."""
    from coupons.models import RestaurantCouponBenefit, StampRewardRule
    from coupons.service import STAMP_DB_ALIAS

    benefit_alias = _db_alias(db_alias)
    stamp_alias = STAMP_DB_ALIAS

    config = dict(CSV_STAMP_RULE_CONFIG)

    if dry_run:
        return True

    for rule in StampRewardRule.objects.using(stamp_alias).filter(
        restaurant_id=RESTAURANT_ID
    ):
        if _is_stamp_disabled_rule_config(rule.config_json):
            rule.delete()

    StampRewardRule.objects.using(stamp_alias).update_or_create(
        restaurant_id=RESTAURANT_ID,
        defaults={
            "rule_type": "THRESHOLD",
            "config_json": config,
            "active": True,
        },
    )
    RestaurantCouponBenefit.objects.using(benefit_alias).filter(
        restaurant_id=RESTAURANT_ID,
        coupon_type__code__startswith="STAMP_REWARD_",
    ).exclude(coupon_type__code__in=FESTIVAL_COUPON_CODES).update(active=True)
    return True


def sync_super_crispy_benefits_summary(*, db_alias: str | None = None) -> None:
    import json

    alias = _db_alias(db_alias)
    from restaurants.benefits_summary import build_coupon_benefits_summary

    summary = build_coupon_benefits_summary(RESTAURANT_ID, db_alias=alias)
    payload = json.dumps(summary, ensure_ascii=False)
    conn = connections[alias]
    with conn.cursor() as cursor:
        if conn.vendor == "postgresql":
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET coupon_benefits_summary = %s::jsonb
                WHERE restaurant_id = %s
                """,
                [payload, RESTAURANT_ID],
            )
        else:
            cursor.execute(
                """
                UPDATE restaurants_affiliate
                SET coupon_benefits_summary = %s
                WHERE restaurant_id = %s
                """,
                [payload, RESTAURANT_ID],
            )


def recover_super_crispy_merchant_data(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
) -> RestoreAudit:
    """
    쿠폰 benefit(299→298), CSV 계약 반영, 스탬프 규칙, 사용자 적립 데이터, summary 복구.
    """
    alias = _db_alias(db_alias)
    work_notes: list[str] = []
    work_notes.append("[DRY-RUN] merchant 복구" if dry_run else "[merchant 복구 시작]")

    n = copy_super_crispy_benefits_from_festival_slot(db_alias=alias, dry_run=dry_run)
    work_notes.append(f"299→298 benefit 복사(대상) {n}건")

    contract_n = apply_super_crispy_contract(db_alias=alias, dry_run=dry_run)
    work_notes.append(f"CSV 계약 benefit 반영 {contract_n}건")

    restore_super_crispy_stamp_rule(db_alias=alias, dry_run=dry_run)
    work_notes.append("298 StampRewardRule·STAMP benefit 복구 (3/5/7/10)")

    user_stats = recover_super_crispy_user_accumulation_data(
        db_alias=alias, dry_run=dry_run
    )
    work_notes.append(
        "사용자 적립 복구: "
        f"wallets={user_stats.get('wallets_moved', 0)}, "
        f"events={user_stats.get('events_moved', 0)}, "
        f"coupons={user_stats.get('coupons_moved', 0)}"
        + (
            f" (299 지갑 {user_stats.get('wallets_at_299', 0)}개, "
            f"스탬프>0 {user_stats.get('wallets_with_stamps', 0)}개)"
            if dry_run
            else ""
        )
    )

    if not dry_run:
        sync_super_crispy_benefits_summary(db_alias=alias)
        work_notes.append("coupon_benefits_summary 갱신")
        apply_super_crispy_pin_from_env(db_alias=alias)

    final = audit_super_crispy(db_alias=alias)
    final.notes = work_notes + final.notes
    issues = verify_super_crispy_against_contract(db_alias=alias)
    if issues and not dry_run:
        final.warnings.extend(issues)
    return final


def complete_super_crispy_recovery(
    *,
    db_alias: str | None = None,
    dry_run: bool = False,
    pin: str | None = None,
) -> RestoreAudit:
    """제휴 행 정리 + merchant·사용자 데이터·CSV 계약 전체 복구."""
    alias = _db_alias(db_alias)
    effective_pin = pin if pin is not None else resolve_super_crispy_pin_from_env()
    restore_super_crispy_affiliate(
        db_alias=alias,
        dry_run=dry_run,
        reset_pin=False,
        pin=effective_pin,
        recover_merchant_data=False,
    )
    return recover_super_crispy_merchant_data(db_alias=alias, dry_run=dry_run)
