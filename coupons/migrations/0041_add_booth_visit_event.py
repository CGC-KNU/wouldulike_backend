from django.db import migrations


def add_booth_visit_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.update_or_create(
        code="BOOTH_VISIT_EVENT",
        defaults={
            "name": "부스 방문 쿠폰 이벤트",
            "type": "REFERRAL",
            "active": True,
            "rules_json": {},
        },
    )


def remove_booth_visit_event(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code="BOOTH_VISIT_EVENT").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0040_fix_stamp_reward_expiry_global"),
    ]

    operations = [
        migrations.RunPython(add_booth_visit_event, remove_booth_visit_event),
    ]

