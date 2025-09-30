
import string
import secrets
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from restaurants.models import AffiliateRestaurant
from coupons.models import MerchantPin


class Command(BaseCommand):
    help = "Generate or refresh static PIN codes for all affiliate restaurants."

    def add_arguments(self, parser):
        parser.add_argument(
            '--length', type=int, default=4,
            help='Length of the generated PIN (default: 4 digits).'
        )
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Regenerate PINs even if a restaurant already has one.'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would change without writing to the database.'
        )

    def handle(self, *args, **options):
        length = options['length']
        overwrite = options['overwrite']
        dry_run = options['dry_run']

        if length < 4:
            self.stderr.write(self.style.ERROR('PIN length must be at least 4.'))
            return

        alphabet = string.digits
        alias = 'cloudsql'
        created = updated = skipped = 0
        used = set(
            MerchantPin.objects.using(alias)
            .exclude(secret__isnull=True)
            .values_list('secret', flat=True)
        )
        used.update(
            pin for pin in
            AffiliateRestaurant.objects.using(alias)
            .exclude(pin_secret__isnull=True)
            .values_list('pin_secret', flat=True)
        )
        used.discard(None)

        def generate_unique():
            for _ in range(100):
                candidate = ''.join(secrets.choice(alphabet) for _ in range(length))
                if candidate not in used:
                    used.add(candidate)
                    return candidate
            raise RuntimeError('Failed to generate unique PIN after multiple attempts.')

        qs = AffiliateRestaurant.objects.using(alias).all()
        total = qs.count()
        self.stdout.write(f'Processing {total} affiliate restaurants...')

        for restaurant in qs.iterator():
            mp = (
                MerchantPin.objects.using(alias)
                .filter(restaurant_id=restaurant.restaurant_id)
                .first()
            )
            existing_pin = None
            if mp and mp.secret:
                existing_pin = mp.secret
            elif restaurant.pin_secret:
                existing_pin = restaurant.pin_secret

            if existing_pin and not overwrite:
                skipped += 1
                continue

            new_pin = generate_unique()

            if dry_run:
                action = 'would update' if existing_pin else 'would create'
                self.stdout.write(
                    f"[{action}] restaurant_id={restaurant.restaurant_id} name={restaurant.name} pin={new_pin}"
                )
                continue

            now = timezone.now()
            with transaction.atomic(using=alias):
                obj, created_flag = MerchantPin.objects.using(alias).update_or_create(
                    restaurant=restaurant,
                    defaults={
                        'algo': 'STATIC',
                        'secret': new_pin,
                        'period_sec': mp.period_sec if mp else 30,
                        'last_rotated_at': now,
                    },
                )
                AffiliateRestaurant.objects.using(alias).filter(
                    restaurant_id=restaurant.restaurant_id
                ).update(pin_secret=new_pin, pin_updated_at=now)

            if created_flag:
                created += 1
            else:
                updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run mode active: no changes were saved.'))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Completed. created={created}, updated={updated}, skipped={skipped}'
            )
        )
