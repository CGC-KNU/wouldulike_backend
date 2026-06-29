from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    OwnerProfile은 이미 DB에 존재하므로 --fake-initial 옵션으로 skip됨.
    AdminConfig는 신규 테이블로 실제 생성됨.
    """

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("restaurants", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="OwnerProfile",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("tier", models.CharField(
                    choices=[("FREE", "Free"), ("BOOST", "Boost"), ("CONTENT", "Content")],
                    default="FREE",
                    max_length=10,
                )),
                ("is_active", models.BooleanField(default=True)),
                ("verified_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("restaurant", models.ForeignKey(
                    db_column="restaurant_id",
                    db_constraint=False,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="owner_profile",
                    to="restaurants.affiliaterestaurant",
                    to_field="restaurant_id",
                )),
                ("user", models.OneToOneField(
                    db_constraint=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="owner_profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "dashboard_owner_profile"},
        ),
    ]
