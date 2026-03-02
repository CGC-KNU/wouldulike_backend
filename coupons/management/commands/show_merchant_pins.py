"""
DB에 저장된 식당별 PIN 번호를 조회합니다.
실제 쿠폰/스탬프 검증에 사용되는 값은 MerchantPin.secret 입니다.
"""
from django.core.management.base import BaseCommand

from coupons.models import MerchantPin
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "DB에 저장된 식당별 PIN 번호 조회"

    def add_arguments(self, parser):
        parser.add_argument(
            "--restaurant-id",
            type=int,
            action="append",
            help="조회할 restaurant_id (여러 개 지정 가능)",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="식당명으로 검색 (부분 일치)",
        )

    def handle(self, *args, **options):
        alias = "cloudsql"
        restaurant_ids = options.get("restaurant_id") or []
        name_filter = options.get("name")

        # 식당 목록 조회
        qs = AffiliateRestaurant.objects.using(alias).all()
        if restaurant_ids:
            qs = qs.filter(restaurant_id__in=restaurant_ids)
        if name_filter:
            qs = qs.filter(name__icontains=name_filter)

        restaurants = {r.restaurant_id: r for r in qs}
        if not restaurants:
            self.stdout.write(self.style.WARNING("조건에 맞는 식당이 없습니다."))
            return

        ids = list(restaurants.keys())
        pins = MerchantPin.objects.using(alias).filter(restaurant_id__in=ids).select_related("restaurant")

        pin_map = {mp.restaurant_id: mp for mp in pins}

        self.stdout.write("=" * 60)
        self.stdout.write("DB 적용된 PIN (MerchantPin.secret = 실제 검증에 사용)")
        self.stdout.write("=" * 60)

        for rid in sorted(ids):
            r = restaurants[rid]
            mp = pin_map.get(rid)
            ar_pin = r.pin_secret
            mp_secret = mp.secret if mp else None

            # 실제 검증은 MerchantPin.secret 사용
            effective = mp_secret or ar_pin or "(없음)"
            self.stdout.write(f"  {rid}: {r.name}")
            self.stdout.write(f"    -> MerchantPin.secret: {mp_secret}")
            self.stdout.write(f"    -> AffiliateRestaurant.pin_secret: {ar_pin}")
            self.stdout.write(f"    -> 실제 사용값: {effective}")
            self.stdout.write("")
