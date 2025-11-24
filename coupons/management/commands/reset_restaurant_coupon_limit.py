"""
식당별 쿠폰 제한 초기화 명령어
사용된 쿠폰(REDEEMED 상태)을 삭제하여 식당별 쿠폰 제한을 다시 200장으로 초기화
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from coupons.models import Coupon
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = '식당별 쿠폰 제한 초기화 (사용된 쿠폰 삭제)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 변경하지 않고 미리보기만 표시',
        )
        parser.add_argument(
            '--restaurant-id',
            type=int,
            help='특정 식당 ID만 초기화 (선택사항)',
        )
        parser.add_argument(
            '--status',
            type=str,
            default='REDEEMED',
            help='삭제할 쿠폰 상태 (기본값: REDEEMED)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        restaurant_id = options.get('restaurant_id')
        status = options['status']
        alias = 'cloudsql'

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY-RUN 모드: 실제 변경 없음 ===\n'))

        # 쿠폰 쿼리 구성
        coupon_query = Coupon.objects.using(alias).filter(status=status)
        
        if restaurant_id:
            coupon_query = coupon_query.filter(restaurant_id=restaurant_id)
            self.stdout.write(f'식당 ID {restaurant_id}의 {status} 상태 쿠폰만 처리합니다.\n')
        else:
            self.stdout.write(f'모든 식당의 {status} 상태 쿠폰을 처리합니다.\n')

        # 삭제될 쿠폰 수
        deleted_count = coupon_query.count()
        self.stdout.write(f'삭제될 쿠폰: {deleted_count}개\n')

        if deleted_count == 0:
            self.stdout.write(self.style.WARNING(f'{status} 상태인 쿠폰이 없습니다.'))
            return

        # 식당별 쿠폰 발급 현황 (삭제 전)
        self.stdout.write('=== 삭제 전 식당별 쿠폰 발급 현황 ===')
        restaurant_coupon_counts_before = (
            Coupon.objects.using(alias)
            .exclude(restaurant_id__isnull=True)
            .values('restaurant_id')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        
        for item in restaurant_coupon_counts_before[:10]:
            self.stdout.write(f'  Restaurant {item["restaurant_id"]}: {item["cnt"]}개')
        
        if restaurant_coupon_counts_before.count() > 10:
            self.stdout.write(f'  ... 외 {restaurant_coupon_counts_before.count() - 10}개 식당\n')
        else:
            self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY-RUN 모드: 실제 삭제하지 않습니다.'))
            return

        # 확인 메시지
        self.stdout.write(self.style.WARNING(f'\n⚠️  {deleted_count}개의 {status} 상태 쿠폰을 삭제합니다. 계속하시겠습니까?'))
        confirm = input('계속하려면 "yes"를 입력하세요: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
            return

        # 실제 삭제
        self.stdout.write('\n쿠폰 삭제 중...')
        
        with transaction.atomic(using=alias):
            deleted = coupon_query.delete()[0]

        # 삭제 후 현황
        self.stdout.write('\n=== 삭제 후 식당별 쿠폰 발급 현황 ===')
        restaurant_coupon_counts_after = (
            Coupon.objects.using(alias)
            .exclude(restaurant_id__isnull=True)
            .values('restaurant_id')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )
        
        for item in restaurant_coupon_counts_after[:10]:
            self.stdout.write(f'  Restaurant {item["restaurant_id"]}: {item["cnt"]}개')
        
        if restaurant_coupon_counts_after.count() > 10:
            self.stdout.write(f'  ... 외 {restaurant_coupon_counts_after.count() - 10}개 식당')

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 초기화 완료 ===\n'
                f'삭제된 쿠폰: {deleted}개'
            )
        )

