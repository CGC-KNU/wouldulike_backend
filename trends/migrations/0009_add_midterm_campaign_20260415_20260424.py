from datetime import datetime

from django.db import migrations
from django.db.models import F
from django.utils import timezone


MIDTERM_INSTAGRAM_URL = "https://www.instagram.com/p/DXI4nzREdnF/?img_index=13&igsh=bG8yNWNpcnhkM21i"
MIDTERM_BANNER_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "banner/midterm_2604_banner.png"
)
MIDTERM_POPUP_IMAGE_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "popup/midterm_2604_popup.png"
)


def _midterm_window_range():
    # 2026-04-15 00:00:00 ~ 2026-04-24 23:59:59 (KST)
    # UTC 저장값: 2026-04-14 15:00:00 ~ 2026-04-24 14:59:59
    start = timezone.make_aware(datetime(2026, 4, 14, 15, 0, 0), timezone.utc)
    end = timezone.make_aware(datetime(2026, 4, 24, 14, 59, 59), timezone.utc)
    return start, end


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    start_at, end_at = _midterm_window_range()

    # 배너(Trend): 최상단에 1개 추가
    Trend.objects.filter(display_order__gte=0).update(display_order=F("display_order") + 1)
    Trend.objects.create(
        title="우주라이크 중간고사 기획전 배너",
        description="중간고사 기획전",
        image=MIDTERM_BANNER_IMAGE_URL,
        blog_link=MIDTERM_INSTAGRAM_URL,
        display_order=0,
    )

    # 팝업(PopupCampaign): 최상단에 1개 추가
    PopupCampaign.objects.filter(display_order__gte=0).update(
        display_order=F("display_order") + 1
    )
    PopupCampaign.objects.create(
        title="우주라이크 중간고사 기획전 팝업창",
        image_url=MIDTERM_POPUP_IMAGE_URL,
        instagram_url=MIDTERM_INSTAGRAM_URL,
        start_at=start_at,
        end_at=end_at,
        is_active=True,
        display_order=0,
    )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    Trend.objects.filter(title="우주라이크 중간고사 기획전 배너").delete()
    Trend.objects.filter(display_order__gte=1).update(display_order=F("display_order") - 1)

    PopupCampaign.objects.filter(title="우주라이크 중간고사 기획전 팝업창").delete()
    PopupCampaign.objects.filter(display_order__gte=1).update(
        display_order=F("display_order") - 1
    )


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0008_fix_date_campaign_main_202604_images"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

