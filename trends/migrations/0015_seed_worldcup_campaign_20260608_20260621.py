from datetime import datetime

from django.db import migrations
from django.db.models import F
from django.utils import timezone


WORLDCUP_MINIGAME_LANDING_URL = "https://aesthetic-valeria-coggiri-a6dca985.koyeb.app/"
WORLDCUP_MINIGAME_BANNER_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "banner/worldcup2026minigame_banner.jpeg"
)
WORLDCUP_MINIGAME_POPUP_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "popup/worldcup2026minigame_popup.jpeg"
)

WORLDCUP_BENEFIT_INSTAGRAM_URL = (
    "https://www.instagram.com/p/DZTvkufko6E/"
    "?utm_source=ig_web_copy_link&igsh=NTc4MTIwNjQ2YQ=="
)
WORLDCUP_BENEFIT_BANNER_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "banner/worldcup2026benefit_banner.jpeg"
)
WORLDCUP_BENEFIT_POPUP_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "popup/worldcup2026benefit_popup.jpeg"
)

WORLDCUP_MINIGAME_BANNER_TITLE = "우주라이크 월드컵 미니게임 배너"
WORLDCUP_MINIGAME_POPUP_TITLE = "우주라이크 월드컵 미니게임 팝업"
WORLDCUP_BENEFIT_BANNER_TITLE = "우주라이크 월드컵 혜택 배너"
WORLDCUP_BENEFIT_POPUP_TITLE = "우주라이크 월드컵 혜택 팝업"


def _worldcup_window_range():
    # 2026-06-08 00:00:00 ~ 2026-06-21 23:59:59 (KST)
    # UTC 저장값: 2026-06-07 15:00:00 ~ 2026-06-21 14:59:59
    start = timezone.make_aware(datetime(2026, 6, 7, 15, 0, 0), timezone.utc)
    end = timezone.make_aware(datetime(2026, 6, 21, 14, 59, 59), timezone.utc)
    return start, end


def _shift_display_order_up(model):
    model.objects.filter(display_order__gte=0).update(
        display_order=F("display_order") + 1
    )


def _shift_display_order_down(model):
    model.objects.filter(display_order__gte=1).update(
        display_order=F("display_order") - 1
    )


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    start_at, end_at = _worldcup_window_range()

    if not Trend.objects.filter(title=WORLDCUP_BENEFIT_BANNER_TITLE).exists():
        _shift_display_order_up(Trend)
        Trend.objects.create(
            title=WORLDCUP_BENEFIT_BANNER_TITLE,
            description="이번 월드컵 뭐 먹으면서 응원하지?",
            image=WORLDCUP_BENEFIT_BANNER_IMAGE_URL,
            blog_link=WORLDCUP_BENEFIT_INSTAGRAM_URL,
            display_order=0,
        )

    if not PopupCampaign.objects.filter(title=WORLDCUP_BENEFIT_POPUP_TITLE).exists():
        _shift_display_order_up(PopupCampaign)
        PopupCampaign.objects.create(
            title=WORLDCUP_BENEFIT_POPUP_TITLE,
            image_url=WORLDCUP_BENEFIT_POPUP_IMAGE_URL,
            instagram_url=WORLDCUP_BENEFIT_INSTAGRAM_URL,
            start_at=start_at,
            end_at=end_at,
            is_active=True,
            display_order=0,
        )

    if not Trend.objects.filter(title=WORLDCUP_MINIGAME_BANNER_TITLE).exists():
        _shift_display_order_up(Trend)
        Trend.objects.create(
            title=WORLDCUP_MINIGAME_BANNER_TITLE,
            description="월드컵 예측하고, 응원하고 맛집 쿠폰 받자!",
            image=WORLDCUP_MINIGAME_BANNER_IMAGE_URL,
            blog_link=WORLDCUP_MINIGAME_LANDING_URL,
            display_order=0,
        )

    if not PopupCampaign.objects.filter(title=WORLDCUP_MINIGAME_POPUP_TITLE).exists():
        _shift_display_order_up(PopupCampaign)
        PopupCampaign.objects.create(
            title=WORLDCUP_MINIGAME_POPUP_TITLE,
            image_url=WORLDCUP_MINIGAME_POPUP_IMAGE_URL,
            instagram_url=WORLDCUP_MINIGAME_LANDING_URL,
            start_at=start_at,
            end_at=end_at,
            is_active=True,
            display_order=0,
        )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    if Trend.objects.filter(title=WORLDCUP_MINIGAME_BANNER_TITLE).exists():
        Trend.objects.filter(title=WORLDCUP_MINIGAME_BANNER_TITLE).delete()
        _shift_display_order_down(Trend)

    if PopupCampaign.objects.filter(title=WORLDCUP_MINIGAME_POPUP_TITLE).exists():
        PopupCampaign.objects.filter(title=WORLDCUP_MINIGAME_POPUP_TITLE).delete()
        _shift_display_order_down(PopupCampaign)

    if Trend.objects.filter(title=WORLDCUP_BENEFIT_BANNER_TITLE).exists():
        Trend.objects.filter(title=WORLDCUP_BENEFIT_BANNER_TITLE).delete()
        _shift_display_order_down(Trend)

    if PopupCampaign.objects.filter(title=WORLDCUP_BENEFIT_POPUP_TITLE).exists():
        PopupCampaign.objects.filter(title=WORLDCUP_BENEFIT_POPUP_TITLE).delete()
        _shift_display_order_down(PopupCampaign)


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0014_update_restaurant_guide_banner_link"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
