from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0023_add_stamp_reward_coupon_types_extended"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurantcouponbenefit",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
