from django.db import migrations


def add_new_semester_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")

    # 신학기 추천코드 이벤트 쿠폰 타입 생성
    CouponType.objects.update_or_create(
        code="NEW_SEMESTER_SPECIAL",
        defaults={
            "title": "신학기 추천코드 이벤트",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )

    # 신학기 이벤트 Campaign 생성
    Campaign.objects.update_or_create(
        code="NEW_SEMESTER_EVENT",
        defaults={
            "name": "신학기 추천코드 이벤트",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
    )


def remove_new_semester_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign.objects.filter(code="NEW_SEMESTER_EVENT").delete()
    CouponType.objects.filter(code="NEW_SEMESTER_SPECIAL").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0027_add_stamp_reward_2_6_9"),
    ]

    operations = [
        migrations.RunPython(add_new_semester_event, remove_new_semester_event),
    ]
