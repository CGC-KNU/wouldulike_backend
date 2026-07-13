from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_add_apple_login_support"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserRestaurantWishlist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("restaurant_id", models.IntegerField(db_index=True)),
                ("restaurant_name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="restaurant_wishlist",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "accounts_user_restaurant_wishlist"},
        ),
        migrations.AddConstraint(
            model_name="userrestaurantwishlist",
            constraint=models.UniqueConstraint(
                fields=["user", "restaurant_id"],
                name="unique_user_restaurant_wishlist",
            ),
        ),
    ]
