from django.db import migrations
from django.utils import timezone


def add_event_reward_campaigns(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    
    # 이벤트 보상 Campaign 2개 생성
    # 1. 신규가입과 동일한 쿠폰 타입(WELCOME_3000) 사용
    Campaign.objects.update_or_create(
        code="EVENT_REWARD_SIGNUP",
        defaults={
            "name": "Event Reward (Signup Type)",
            "type": "REFERRAL",  # 기존 타입 재사용
            "active": True,
            "rules_json": {},
        },
    )
    
    # 2. 친구초대와 동일한 쿠폰 타입(REFERRAL_BONUS_REFEREE) 사용
    Campaign.objects.update_or_create(
        code="EVENT_REWARD_REFERRAL",
        defaults={
            "name": "Event Reward (Referral Type)",
            "type": "REFERRAL",  # 기존 타입 재사용
            "active": True,
            "rules_json": {},
        },
    )


def remove_event_reward_campaigns(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code__in=["EVENT_REWARD_SIGNUP", "EVENT_REWARD_REFERRAL"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0009_update_coupon_type_policy"),
    ]

    operations = [
        migrations.RunPython(add_event_reward_campaigns, remove_event_reward_campaigns),
    ]

