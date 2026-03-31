from django.db import migrations


def add_medium_rare_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.update_or_create(
        code="MEDIUM_RARE_EVENT",
        defaults={
            "name": "미디움레어 쿠폰 이벤트",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
    )


def remove_medium_rare_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="MEDIUM_RARE_EVENT").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0042_add_roulette_events"),
    ]

    operations = [
        migrations.RunPython(add_medium_rare_event, remove_medium_rare_event),
    ]

