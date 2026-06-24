"""종강 기획전 benefit 7곳 동기화 (CSV v2: 정든밤·구구포차 추가)."""

import importlib

from django.db import migrations
from django.db.utils import OperationalError, ProgrammingError


def sync_jonggang_benefits(apps, schema_editor):
    mod = importlib.import_module("coupons.migrations.0090_add_jonggang_event_coupon_types")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    jonggang_type = CouponType.objects.filter(code=mod.JONGGANG_COUPON_TYPE_CODE).first()
    if not jonggang_type:
        return

    try:
        restaurants = list(
            AffiliateRestaurant.objects.all().values("restaurant_id", "name")
        )
    except (OperationalError, ProgrammingError):
        return

    mod._upsert_benefits(
        coupon_type=jonggang_type,
        subtitle=mod.JONGGANG_SUBTITLE,
        benefits=mod.JONGGANG_BENEFITS,
        all_restaurants=restaurants,
        benefit_model=RestaurantCouponBenefit,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0091_activate_jonggang_event_app_open_daily"),
    ]

    operations = [
        migrations.RunPython(sync_jonggang_benefits, migrations.RunPython.noop),
    ]
