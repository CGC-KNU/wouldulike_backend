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

MIDTERM_BANNER_TITLE = "우주라이크 중간고사 기획전 배너"
MIDTERM_POPUP_TITLE = "우주라이크 중간고사 기획전 팝업창"


def _midterm_window_range():
    # 2026-04-15 00:00:00 ~ 2026-04-24 23:59:59 (KST)
    # UTC 저장값: 2026-04-14 15:00:00 ~ 2026-04-24 14:59:59
    start = timezone.make_aware(datetime(2026, 4, 14, 15, 0, 0), timezone.utc)
    end = timezone.make_aware(datetime(2026, 4, 24, 14, 59, 59), timezone.utc)
    return start, end


def forward(apps, schema_editor):
    """
    안전장치용 시드 마이그레이션.
    - 특정 환경에서 0009가 부분 적용된 경우를 대비해, 배너/팝업이 없으면 생성한다.
    - 기존 순서를 크게 흔들지 않기 위해 display_order=0 항목만 1칸 밀고, 신규 항목을 0에 둔다.
    """
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    start_at, end_at = _midterm_window_range()

    if not Trend.objects.filter(title=MIDTERM_BANNER_TITLE).exists():
        Trend.objects.filter(display_order=0).update(display_order=F("display_order") + 1)
        Trend.objects.create(
            title=MIDTERM_BANNER_TITLE,
            description="중간고사 기획전",
            image=MIDTERM_BANNER_IMAGE_URL,
            blog_link=MIDTERM_INSTAGRAM_URL,
            display_order=0,
        )

    if not PopupCampaign.objects.filter(title=MIDTERM_POPUP_TITLE).exists():
        PopupCampaign.objects.filter(display_order=0).update(
            display_order=F("display_order") + 1
        )
        PopupCampaign.objects.create(
            title=MIDTERM_POPUP_TITLE,
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
    Trend.objects.filter(title=MIDTERM_BANNER_TITLE).delete()
    PopupCampaign.objects.filter(title=MIDTERM_POPUP_TITLE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("trends", "0009_add_midterm_campaign_20260415_20260424"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]

