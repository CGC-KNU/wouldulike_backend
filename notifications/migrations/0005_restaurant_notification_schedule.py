from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_notification_dedupe_key_and_sent_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RestaurantNotificationSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("restaurant_id", models.IntegerField(db_index=True)),
                ("restaurant_name", models.CharField(max_length=255)),
                ("date", models.DateField(db_index=True)),
                ("slot", models.CharField(choices=[("noon", "정오 (12:00)"), ("evening", "저녁 (18:00)")], max_length=10)),
                ("content", models.TextField()),
                ("scheduled_datetime", models.DateTimeField(db_index=True)),
                ("sent", models.BooleanField(db_index=True, default=False)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="restaurant_notification_schedules",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "notifications_restaurant_schedule"},
        ),
        migrations.AddConstraint(
            model_name="restaurantnotificationschedule",
            constraint=models.UniqueConstraint(
                fields=["restaurant_id", "date", "slot"],
                name="unique_restaurant_date_slot",
            ),
        ),
    ]
