from django.db import migrations


def add_roulette_events(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")

    codes = ["MINYEOL", "EUNJIN", "JAEMIN", "CHAERIN"]
    for code in codes:
        Campaign.objects.update_or_create(
            code=f"ROULETTE_{code}_EVENT",
            defaults={
                "name": f"룰렛 이벤트 쿠폰({code})",
                "type": "REFERRAL",
                "active": True,
                "rules_json": {},
            },
        )


def remove_roulette_events(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code__in=[
        "ROULETTE_MINYEOL_EVENT",
        "ROULETTE_EUNJIN_EVENT",
        "ROULETTE_JAEMIN_EVENT",
        "ROULETTE_CHAERIN_EVENT",
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0041_add_booth_visit_event"),
    ]

    operations = [
        migrations.RunPython(add_roulette_events, remove_roulette_events),
    ]

