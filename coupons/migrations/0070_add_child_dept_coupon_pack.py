from django.db import migrations


def add_child_dept_event(apps, schema_editor):
    from coupons.child_dept_event import ensure_child_dept_event_data

    ensure_child_dept_event_data(db_alias=schema_editor.connection.alias)


def revert_child_dept_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    RestaurantCouponBenefit = apps.get_model("coupons", "RestaurantCouponBenefit")

    child_type = CouponType.objects.filter(code="CHILD_DEPT_COUPON_PACK").first()
    if child_type:
        RestaurantCouponBenefit.objects.filter(coupon_type=child_type).delete()
    Campaign.objects.filter(code="CHILD_DEPT_COUPON_PACK_202605").update(
        active=False,
        start_at=None,
        end_at=None,
    )
    CouponType.objects.filter(code="CHILD_DEPT_COUPON_PACK").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0069_jungdunbam_stamp_display_rewards"),
        ("restaurants", "0005_affiliaterestaurant_description"),
    ]

    operations = [
        migrations.RunPython(add_child_dept_event, revert_child_dept_event),
    ]
