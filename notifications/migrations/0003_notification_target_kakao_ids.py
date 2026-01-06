from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_notification_sent"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="target_kakao_ids",
            field=models.JSONField(null=True, blank=True),
        ),
    ]


