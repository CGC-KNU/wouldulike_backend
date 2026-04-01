from datetime import datetime

from django.db import migrations
from django.db.models import F
from django.utils import timezone


def _popup_window_range():
    start = timezone.make_aware(datetime(2026, 4, 1, 0, 0, 0), timezone.utc)
    end = timezone.make_aware(datetime(2026, 4, 30, 23, 59, 59), timezone.utc)
    return start, end


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    start_at, end_at = _popup_window_range()

    # 트렌드 배너: 게임 1번(맨 앞), 메인 2번 — add_trend_first와 동일한 순서
    Trend.objects.filter(display_order__gte=0).update(display_order=F("display_order") + 1)
    Trend.objects.create(
        title="데이트 기획전 게임 202604 배너",
        description="데이트 기획전 게임 202604",
        image="https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/banner/datecampaigngame2604_banner.png",
        blog_link="https://blank-idelle-coggiri-1527fb3e.koyeb.app/",
        display_order=0,
    )
    Trend.objects.filter(display_order__gte=1).update(display_order=F("display_order") + 1)
    Trend.objects.create(
        title="데이트 기획전 202604 배너",
        description="데이트 기획전 202604",
        image="https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/banner/datecampaignmain2604_banner.png",
        blog_link="https://www.instagram.com/p/DWkk9GpEf6x/?igsh=MWswZWZleGVjd2pxZA==",
        display_order=1,
    )

    # 팝업: 게임 display_order 0, 메인 1 — 기존 항목은 뒤로 밀기
    PopupCampaign.objects.filter(display_order__gte=0).update(display_order=F("display_order") + 2)
    PopupCampaign.objects.create(
        title="데이트 기획전 게임 202604 팝업창",
        image_url="https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/popup/datecampaigngame2604_popup.png",
        instagram_url="https://blank-idelle-coggiri-1527fb3e.koyeb.app/",
        start_at=start_at,
        end_at=end_at,
        is_active=True,
        display_order=0,
    )
    PopupCampaign.objects.create(
        title="데이트 기획전 202604 팝업창",
        image_url="https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/popup/datecampaignmain2604_popup.png",
        instagram_url="https://www.instagram.com/p/DWkk9GpEf6x/?igsh=MWswZWZleGVjd2pxZA==",
        start_at=start_at,
        end_at=end_at,
        is_active=True,
        display_order=1,
    )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")

    trend_titles = (
        "데이트 기획전 게임 202604 배너",
        "데이트 기획전 202604 배너",
    )
    Trend.objects.filter(title__in=trend_titles).delete()
    Trend.objects.filter(display_order__gte=2).update(display_order=F("display_order") - 2)

    popup_titles = (
        "데이트 기획전 게임 202604 팝업창",
        "데이트 기획전 202604 팝업창",
    )
    PopupCampaign.objects.filter(title__in=popup_titles).delete()
    PopupCampaign.objects.filter(display_order__gte=2).update(display_order=F("display_order") - 2)


class Migration(migrations.Migration):

    dependencies = [
        ("trends", "0006_alter_trend_options"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
