from django.db import migrations
from django.utils import timezone


def add_final_exam_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    
    # 기말고사 특별 발급 쿠폰 타입 생성
    CouponType.objects.update_or_create(
        code="FINAL_EXAM_SPECIAL",
        defaults={
            "title": "기말고사 특별 발급 쿠폰",
            "valid_days": 0,
            "per_user_limit": 1,
            "benefit_json": {"type": "fixed", "value": 3000},
        },
    )
    
    # 기말고사 이벤트 Campaign 생성
    Campaign.objects.update_or_create(
        code="FINAL_EXAM_EVENT",
        defaults={
            "name": "기말고사 특별 이벤트",
            "type": "REFERRAL",  # 기존 타입 재사용
            "active": True,
            "rules_json": {},
        },
    )


def remove_final_exam_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    CouponType = apps.get_model("coupons", "CouponType")
    Campaign.objects.filter(code="FINAL_EXAM_EVENT").delete()
    CouponType.objects.filter(code="FINAL_EXAM_SPECIAL").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0013_change_referral_referee_to_foreignkey"),
    ]

    operations = [
        migrations.RunPython(add_final_exam_event, remove_final_exam_event),
    ]

