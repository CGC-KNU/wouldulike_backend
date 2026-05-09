from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_notification_target_kakao_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="dedupe_key",
            field=models.CharField(
                max_length=120,
                null=True,
                blank=True,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="sent_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]

