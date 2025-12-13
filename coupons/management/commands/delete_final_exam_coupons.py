from django.core.management.base import BaseCommand
from django.db import transaction, router
from coupons.models import Coupon, CouponType, Campaign


class Command(BaseCommand):
    help = "기말고사 특별 발급 쿠폰을 모두 삭제합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 삭제하지 않고 삭제될 쿠폰 수만 확인합니다',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='확인 없이 바로 삭제합니다',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_input = options['no_input']
        
        alias = router.db_for_write(Coupon)
        
        try:
            ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
            camp = Campaign.objects.using(alias).get(code="FINAL_EXAM_EVENT", active=True)
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_SPECIAL 쿠폰 타입을 찾을 수 없습니다."))
            return
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_EVENT 캠페인을 찾을 수 없습니다."))
            return
        
        # 삭제될 쿠폰 조회
        coupon_query = Coupon.objects.using(alias).filter(
            coupon_type=ct,
            campaign=camp,
        )
        
        deleted_count = coupon_query.count()
        
        if deleted_count == 0:
            self.stdout.write(self.style.SUCCESS("삭제할 기말고사 쿠폰이 없습니다."))
            return
        
        # 상태별 통계
        status_counts = coupon_query.values('status').annotate(
            count=__import__('django.db.models', fromlist=['Count']).Count('id')
        )
        
        self.stdout.write(f'\n=== 삭제 예정 쿠폰 현황 ===')
        self.stdout.write(f'총 쿠폰 수: {deleted_count}개')
        self.stdout.write('\n상태별 분포:')
        for item in status_counts:
            self.stdout.write(f'  {item["status"]}: {item["count"]}개')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] 실제로 삭제하지 않습니다.'))
            return
        
        # 확인 메시지
        if not no_input:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {deleted_count}개의 기말고사 쿠폰을 삭제합니다. 계속하시겠습니까?'))
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
                return
        
        # 실제 삭제
        self.stdout.write('\n쿠폰 삭제 중...')
        
        with transaction.atomic(using=alias):
            deleted = coupon_query.delete()[0]
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 삭제 완료 ===\n'
                f'삭제된 쿠폰: {deleted}개'
            )
        )

