"""월드컵 제휴 쿠폰 신청폼 일괄 발급 캠페인."""

from django.db import migrations

from coupons.world_cup_partner_event import WORLD_CUP_PARTNER_CAMPAIGN_CODE


def forward(apps, schema_editor):
    from coupons.world_cup_partner_event import ensure_world_cup_partner_event_data

    ensure_world_cup_partner_event_data(db_alias=schema_editor.connection.alias)


def backward(apps, schema_editor):
    Campaign = apps.get_model("coupons", "Campaign")
    Campaign.objects.filter(code=WORLD_CUP_PARTNER_CAMPAIGN_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coupons", "0088_world_cup_app_open_daily_three"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
