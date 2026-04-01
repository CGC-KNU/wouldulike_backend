from django.db import migrations


FULL_SUBTITLE = "[🎈가두모집 쿠폰팩🎈]"

# REFERRAL_BONUS_REFEREE가 있으면 해당 식당의 모든 행을 복사(0034와 동일).
# 없으면 아래 순서로 첫 행만 복사.
_FALLBACK_CODES_ORDERED = [
    "WELCOME_3000",
    "REFERRAL_BONUS_REFERRER",
    "DATELIKE",
    "APP_OPEN_SPECIAL_20260329",
    "MIDTERM_EVENT_SPECIAL",
    "DATE_EVENT_SPECIAL",
]


def _db_alias(schema_editor):
    return schema_editor.connection.alias


def sync_full_affiliate_benefits(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    if "restaurants_affiliate" not in table_names:
        # 로컬 SQLite 테스트 등 Affiliate 테이블이 없는 DB는 건너뜀
        return

    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    alias = _db_alias(schema_editor)
    qs = RestaurantCouponBenefit.objects.db_manager(alias)

    try:
        full_ct = CouponType.objects.db_manager(alias).get(code="FULL_AFFILIATE_SPECIAL")
        ref_referee_ct = CouponType.objects.db_manager(alias).get(code="REFERRAL_BONUS_REFEREE")
    except CouponType.DoesNotExist:
        return

    # 마이그레이션 스냅샷에 is_affiliate 필드가 없을 수 있어 실제 테이블에서 조회
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT restaurant_id FROM restaurants_affiliate WHERE is_affiliate IS TRUE"
        )
        aff_ids = {row[0] for row in cursor.fetchall()}
    has_full = set(
        qs.filter(coupon_type=full_ct, active=True).values_list("restaurant_id", flat=True)
    )
    has_any_other = set(
        qs.filter(active=True).exclude(coupon_type=full_ct).values_list("restaurant_id", flat=True)
    )

    candidates = sorted((aff_ids - has_full) & has_any_other)
    if not candidates:
        return

    for rid in candidates:
        ref_rows = list(
            qs.filter(
                coupon_type=ref_referee_ct,
                restaurant_id=rid,
                active=True,
            ).order_by("sort_order", "id")
        )
        if ref_rows:
            for src in ref_rows:
                qs.update_or_create(
                    coupon_type=full_ct,
                    restaurant_id=rid,
                    sort_order=getattr(src, "sort_order", 0),
                    defaults={
                        "title": src.title,
                        "subtitle": FULL_SUBTITLE,
                        "benefit_json": src.benefit_json or {},
                        "notes": getattr(src, "notes", "") or "",
                        "active": True,
                    },
                )
            continue

        src = None
        for code in _FALLBACK_CODES_ORDERED:
            try:
                ct = CouponType.objects.db_manager(alias).get(code=code)
            except CouponType.DoesNotExist:
                continue
            src = (
                qs.filter(coupon_type=ct, restaurant_id=rid, active=True)
                .order_by("sort_order", "id")
                .first()
            )
            if src:
                break
        if not src:
            src = (
                qs.filter(
                    restaurant_id=rid,
                    active=True,
                    coupon_type__code__startswith="STAMP_",
                )
                .order_by("sort_order", "id")
                .first()
            )
        if not src:
            continue

        qs.update_or_create(
            coupon_type=full_ct,
            restaurant_id=rid,
            sort_order=getattr(src, "sort_order", 0),
            defaults={
                "title": src.title,
                "subtitle": FULL_SUBTITLE,
                "benefit_json": src.benefit_json or {},
                "notes": getattr(src, "notes", "") or "",
                "active": True,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0043_add_medium_rare_event"),
    ]

    operations = [
        migrations.RunPython(sync_full_affiliate_benefits, noop_reverse),
    ]
