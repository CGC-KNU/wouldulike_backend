from django.db import migrations, models


def set_initial_display_order(apps, schema_editor):
    """기존 트렌드에 created_at 기준으로 display_order 순서 부여 (최신순 = 0)"""
    Trend = apps.get_model("trends", "Trend")
    for idx, trend in enumerate(Trend.objects.order_by("-created_at")):
        trend.display_order = idx
        trend.save()


class Migration(migrations.Migration):

    dependencies = [
        ("trends", "0004_popupcampaign"),
    ]

    operations = [
        migrations.AddField(
            model_name="trend",
            name="display_order",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(set_initial_display_order, migrations.RunPython.noop),
    ]
