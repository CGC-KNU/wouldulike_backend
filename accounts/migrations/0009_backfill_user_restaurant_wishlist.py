"""
Data migration: backfill UserRestaurantWishlist from existing User.favorite_restaurants JSON.

User.favorite_restaurants stores a JSON array of restaurant_id strings, e.g. '["30", "45", "82"]'.
We iterate all users with non-empty favorite_restaurants, look up the restaurant name from
AffiliateRestaurant (CloudSQL, read via 'cloudsql' DB router), and insert UserRestaurantWishlist
rows for any that don't already exist.
"""

import json
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_wishlist(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserRestaurantWishlist = apps.get_model("accounts", "UserRestaurantWishlist")
    AffiliateRestaurant = apps.get_model("restaurants", "AffiliateRestaurant")

    # Pre-load restaurant name map (CloudSQL)
    restaurant_names: dict[int, str] = {}
    try:
        for r in AffiliateRestaurant.objects.using("cloudsql").only("restaurant_id", "name"):
            restaurant_names[r.restaurant_id] = r.name
    except Exception:
        logger.warning("Could not load AffiliateRestaurant names during backfill — names will be placeholder")

    created = 0
    skipped = 0

    for user in User.objects.exclude(favorite_restaurants__isnull=True).exclude(favorite_restaurants="").exclude(favorite_restaurants="[]"):
        try:
            raw = user.favorite_restaurants
            if not raw:
                continue
            ids = json.loads(raw)
            if not isinstance(ids, list):
                continue
        except (json.JSONDecodeError, TypeError):
            continue

        for id_str in ids:
            try:
                rid = int(id_str)
            except (ValueError, TypeError):
                continue

            r_name = restaurant_names.get(rid, f"식당#{rid}")

            _, was_created = UserRestaurantWishlist.objects.get_or_create(
                user=user,
                restaurant_id=rid,
                defaults={"restaurant_name": r_name},
            )
            if was_created:
                created += 1
            else:
                skipped += 1

    logger.info("UserRestaurantWishlist backfill complete: created=%d, already_existed=%d", created, skipped)


def reverse_backfill(apps, schema_editor):
    # 역방향 마이그레이션은 no-op (데이터 손실 방지)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_user_restaurant_wishlist"),
        ("restaurants", "0004_affiliaterestaurant"),
    ]

    operations = [
        migrations.RunPython(backfill_wishlist, reverse_backfill),
    ]
