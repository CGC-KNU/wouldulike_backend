from datetime import datetime

from django.db import migrations
from django.db.models import F
from django.utils import timezone


SUMMER_MINIGAME_LANDING_URL = "https://permanent-kelley-coggiri-3f157565.koyeb.app/"
SUMMER_MINIGAME_BANNER_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "banner/summer_minigame_banner.jpeg"
)
SUMMER_MINIGAME_POPUP_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "popup/summer_minigame_popup.jpeg"
)

SUMMER_MINIGAME_BANNER_TITLE = "우주라이크 여름맞이 미니게임 배너"
SUMMER_MINIGAME_POPUP_TITLE = "우주라이크 여름맞이 미니게임 팝업"


def _summer_minigame_window_range():
    # 2026-05-22 00:00:00 ~ 2026-06-07 23:59:59 (KST)
    # UTC 저장값: 2026-05-21 15:00:00 ~ 2026-06-07 14:59:59
    start = timezone.make_aware(datetime(2026, 5, 21, 15, 0, 0), timezone.utc)
    end = timezone.make_aware(datetime(2026, 6, 7, 14, 59, 59), timezone.utc)
    return start, end


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    start_at, end_at = _summer_minigame_window_range()

    if not Trend.objects.filter(title=SUMMER_MINIGAME_BANNER_TITLE).exists():
        Trend.objects.filter(display_order__gte=0).update(
            display_order=F("display_order") + 1
        )
        Trend.objects.create(
            title=SUMMER_MINIGAME_BANNER_TITLE,
            description="여름맞이 3종 미니게임 클리어하고 쿠폰 받기",
            image=SUMMER_MINIGAME_BANNER_IMAGE_URL,
            blog_link=SUMMER_MINIGAME_LANDING_URL,
            display_order=0,
        )

    if not PopupCampaign.objects.filter(title=SUMMER_MINIGAME_POPUP_TITLE).exists():
        PopupCampaign.objects.filter(display_order__gte=0).update(
            display_order=F("display_order") + 1
        )
        PopupCampaign.objects.create(
            title=SUMMER_MINIGAME_POPUP_TITLE,
            image_url=SUMMER_MINIGAME_POPUP_IMAGE_URL,
            instagram_url=SUMMER_MINIGAME_LANDING_URL,
            start_at=start_at,
            end_at=end_at,
            is_active=True,
            display_order=0,
        )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    if Trend.objects.filter(title=SUMMER_MINIGAME_BANNER_TITLE).exists():
        Trend.objects.filter(title=SUMMER_MINIGAME_BANNER_TITLE).delete()
        Trend.objects.filter(display_order__gte=1).update(
            display_order=F("display_order") - 1
        )

    if PopupCampaign.objects.filter(title=SUMMER_MINIGAME_POPUP_TITLE).exists():
        PopupCampaign.objects.filter(title=SUMMER_MINIGAME_POPUP_TITLE).delete()
        PopupCampaign.objects.filter(display_order__gte=1).update(
            display_order=F("display_order") - 1
        )


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0012_update_summer_campaign_instagram_link"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

