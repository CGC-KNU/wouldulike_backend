"""여름맞이 기획전 앱 접속 일일 랜덤 1장 발급 캠페인 활성화."""

from django.db import migrations


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="SUMMER_EVENT_APP_OPEN").update(
        active=True,
        rules_json={"trigger": "APP_OPEN", "mode": "DAILY_RANDOM_ONE"},
    )


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="SUMMER_EVENT_APP_OPEN").update(
        active=False,
        rules_json={"trigger": "APP_OPEN"},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0078_add_summer_worldcup_event_coupon_types"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
