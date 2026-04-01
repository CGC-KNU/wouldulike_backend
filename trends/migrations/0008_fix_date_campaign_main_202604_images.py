from django.db import migrations

MAIN_BANNER_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "banner/datecampaignmain2604_banner.png"
)
MAIN_POPUP_URL = (
    "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
    "popup/datecampaignmain2604_popup.png"
)


def forward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    Trend.objects.filter(title="데이트 기획전 202604 배너").update(image=MAIN_BANNER_URL)
    PopupCampaign.objects.filter(title="데이트 기획전 202604 팝업창").update(
        image_url=MAIN_POPUP_URL
    )


def backward(apps, schema_editor):
    Trend = apps.get_model("trends", "Trend")
    PopupCampaign = apps.get_model("trends", "PopupCampaign")
    Trend.objects.filter(title="데이트 기획전 202604 배너").update(
        image=(
            "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
            "popup/datecampaignmain2604_popup.png"
        )
    )
    PopupCampaign.objects.filter(title="데이트 기획전 202604 팝업창").update(
        image_url=(
            "https://wouldulike-default-bucket-lunching.s3.ap-northeast-2.amazonaws.com/"
            "banner/datecampaignmain2604_banner.png"
        )
    )


class Migration(migrations.Migration):

    dependencies = [
        ("trends", "0007_seed_date_campaign_202604"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
