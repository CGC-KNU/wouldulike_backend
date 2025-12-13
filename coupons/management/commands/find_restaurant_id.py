from django.core.management.base import BaseCommand
from restaurants.models import AffiliateRestaurant
from django.db import router


class Command(BaseCommand):
    help = "식당 이름으로 restaurant_id를 찾습니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='찾을 식당 이름 (부분 일치 가능)',
        )

    def handle(self, *args, **options):
        name = options['name']
        
        db_alias = router.db_for_read(AffiliateRestaurant)
        
        # 이름으로 검색
        restaurants = AffiliateRestaurant.objects.using(db_alias).filter(
            name__icontains=name
        )
        
        if not restaurants.exists():
            # CloudSQL에서도 시도
            try:
                restaurants = AffiliateRestaurant.objects.using('cloudsql').filter(
                    name__icontains=name
                )
            except Exception:
                pass
        
        if restaurants.exists():
            self.stdout.write(f'\n"{name}" 검색 결과:')
            self.stdout.write('=' * 60)
            for restaurant in restaurants:
                self.stdout.write(f'Restaurant ID: {restaurant.restaurant_id}')
                self.stdout.write(f'이름: {restaurant.name}')
                self.stdout.write('-' * 60)
        else:
            self.stdout.write(self.style.WARNING(f'"{name}"에 해당하는 식당을 찾을 수 없습니다.'))

