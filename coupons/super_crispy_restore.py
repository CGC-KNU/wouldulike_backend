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
DEFAULT_CATEGORY = "기타"
DEFAULT_ZONE = "북문"

FESTIVAL_NAME_MARKERS = ("정든밤", "우주라이크 X", "우주라이크X")
FESTIVAL_PIN = "0629"
FESTIVAL_COUPON_CODES = frozenset({"JUNGDUNBAM_FESTIVAL_WED"})


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
                    zone = COALESCE(zone, %s)
                WHERE restaurant_id = %s
                """,
                [new_name, new_desc, new_category, DEFAULT_ZONE, RESTAURANT_ID],
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

        # 축제용 스탬프 규칙 제거
        cursor.execute(
            """
            UPDATE coupons_stamprewardrule
            SET active = FALSE
            WHERE restaurant_id = %s
            """,
            [RESTAURANT_ID],
        )

        if reset_pin or pin_is_festival:
            cursor.execute(
                "DELETE FROM coupons_merchantpin WHERE restaurant_id = %s",
                [RESTAURANT_ID],
            )

    if pin:
        apply_super_crispy_pin(db_alias=alias, pin=pin, dry_run=False)
        audit.notes.append("PIN 설정 완료 (MerchantPin·affiliate)")

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
