"""월드컵 기획전 앱 접속 일일 랜덤 3장 발급으로 rules_json 갱신."""

from django.db import migrations


def forward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        rules_json={
            "trigger": "APP_OPEN",
            "mode": "DAILY_RANDOM_PACK",
            "count": 3,
        },
    )


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="WORLD_CUP_EVENT_APP_OPEN").update(
        rules_json={
            "trigger": "APP_OPEN",
            "mode": "DAILY_RANDOM_ONE",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0087_update_world_cup_event_subtitle"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
