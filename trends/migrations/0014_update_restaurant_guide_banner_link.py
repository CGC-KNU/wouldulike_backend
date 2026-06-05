from django.db import migrations


RESTAURANT_GUIDE_BANNER_TITLE = "2026 제휴식당 소개"

OLD_INSTAGRAM_URL = (
    "https://www.instagram.com/p/DVZ9m0PEgJR/?igsh=MWRzMmZtem1nYXFpcw=="
)
NEW_INSTAGRAM_URL = (
    "https://www.instagram.com/p/DXnrWqmkXmO/?igsh=NjlkZzF4cnp1amF0"
)


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    Trend.objects.filter(title=RESTAURANT_GUIDE_BANNER_TITLE).update(
        blog_link=NEW_INSTAGRAM_URL
    )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    Trend.objects.filter(title=RESTAURANT_GUIDE_BANNER_TITLE).update(
        blog_link=OLD_INSTAGRAM_URL
    )


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0013_seed_summer_minigame_campaign_20260522_20260607"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
