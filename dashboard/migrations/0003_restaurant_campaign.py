from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0002_admin_config"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RestaurantCampaignWeekConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("week_start", models.DateField(blank=True, null=True, unique=True)),
                ("max_slots", models.IntegerField(default=5)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "dashboard_campaign_week_config"},
        ),
        migrations.CreateModel(
            name="RestaurantPlanCampaignLimit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("plan_name", models.CharField(max_length=20, unique=True)),
                ("max_per_month", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "dashboard_plan_campaign_limit"},
        ),
        migrations.CreateModel(
            name="RestaurantCampaignApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("restaurant_id", models.IntegerField(db_index=True)),
                ("restaurant_name", models.CharField(max_length=255)),
                ("week_start", models.DateField(db_index=True)),
                ("coupon_title", models.CharField(max_length=120)),
                ("coupon_subtitle", models.CharField(blank=True, default="", max_length=255)),
                ("coupon_notes", models.TextField(blank=True, default="")),
                ("benefit_type", models.CharField(
                    choices=[("PERCENT", "할인율(%)"), ("FIXED", "할인금액(원)"), ("FREE", "무료 제공"), ("OTHER", "기타")],
                    default="OTHER", max_length=10,
                )),
                ("benefit_value", models.IntegerField(blank=True, null=True)),
                ("campaign_description", models.TextField(blank=True, default="")),
                ("status", models.CharField(
                    choices=[
                        ("PENDING", "신청 대기"), ("APPROVED", "승인"),
                        ("REJECTED", "반려"), ("REJECTED_HOLD", "반려(슬롯 보유)"),
                        ("CANCELLED", "취소"),
                    ],
                    default="PENDING", max_length=20,
                )),
                ("admin_notes", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("applied_by", models.ForeignKey(
                    blank=True, db_constraint=False, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="campaign_applications",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True, db_constraint=False, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="reviewed_campaign_applications",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "dashboard_restaurant_campaign_application", "ordering": ["-week_start", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="restaurantcampaignapplication",
            constraint=models.UniqueConstraint(
                fields=["restaurant_id", "week_start"],
                name="uq_campaign_restaurant_week",
            ),
        ),
    ]
