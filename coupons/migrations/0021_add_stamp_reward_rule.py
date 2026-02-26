from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0020_alter_couponrestaurantexclusion_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="StampRewardRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("restaurant_id", models.IntegerField(db_index=True, unique=True)),
                ("rule_type", models.CharField(choices=[("THRESHOLD", "Threshold"), ("VISIT", "Visit")], max_length=20)),
                ("config_json", models.JSONField(default=dict)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
