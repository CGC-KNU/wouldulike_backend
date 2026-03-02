# Generated manually for multiple coupons per restaurant support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0025_update_coupon_expiry_to_2026_07"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurantcouponbenefit",
            name="sort_order",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RemoveConstraint(
            model_name="restaurantcouponbenefit",
            name="uq_coupon_type_restaurant",
        ),
        migrations.AddConstraint(
            model_name="restaurantcouponbenefit",
            constraint=models.UniqueConstraint(
                fields=["coupon_type", "restaurant", "sort_order"],
                name="uq_coupon_type_restaurant_sort",
            ),
        ),
    ]
