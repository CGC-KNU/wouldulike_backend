from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trends", "0003_alter_trend_image"),
    ]

    operations = [
        migrations.CreateModel(
            name="PopupCampaign",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("image_url", models.URLField(max_length=500)),
                ("instagram_url", models.URLField(max_length=500)),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "popup_campaigns",
                "ordering": ("display_order", "-created_at"),
            },
        ),
        migrations.AddConstraint(
            model_name="popupcampaign",
            constraint=models.CheckConstraint(
                check=models.Q(("end_at__gt", models.F("start_at"))),
                name="popup_campaigns_end_at_after_start_at",
            ),
        ),
    ]
