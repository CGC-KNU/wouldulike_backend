from django.db import migrations


SUMMER_BANNER_TITLE = "우주라이크 여름맞이 캠페인 배너"
SUMMER_POPUP_TITLE = "우주라이크 여름맞이 캠페인 팝업"

OLD_INSTAGRAM_URL = (
    "https://www.instagram.com/p/DYoS3QfkS9A/?igsh=MTUycmJodnZwMXJiNQ=="
)
NEW_INSTAGRAM_URL = (
    "https://www.instagram.com/p/DYt5yYakbTX/?igsh=M3djaGRsdDNlcnZ0"
)


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    Trend.objects.filter(title=SUMMER_BANNER_TITLE).update(
        blog_link=NEW_INSTAGRAM_URL
    )
    PopupCampaign.objects.filter(title=SUMMER_POPUP_TITLE).update(
        instagram_url=NEW_INSTAGRAM_URL
    )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    Trend.objects.filter(title=SUMMER_BANNER_TITLE).update(
        blog_link=OLD_INSTAGRAM_URL
    )
    PopupCampaign.objects.filter(title=SUMMER_POPUP_TITLE).update(
        instagram_url=OLD_INSTAGRAM_URL
    )


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0011_seed_summer_campaign_20260522_20260831"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
