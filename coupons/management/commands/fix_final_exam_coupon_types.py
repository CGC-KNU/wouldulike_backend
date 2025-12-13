from django.core.management.base import BaseCommand
from django.db import transaction, router
from coupons.models import Coupon, CouponType, Campaign


class Command(BaseCommand):
    help = "기말고사 쿠폰의 쿠폰 타입을 FINAL_EXAM_SPECIAL로 수정합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 수정하지 않고 수정될 쿠폰 수만 확인합니다',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='확인 없이 바로 수정합니다',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_input = options['no_input']
        
        alias = router.db_for_write(Coupon)
        
        try:
            final_exam_ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
            final_exam_camp = Campaign.objects.using(alias).get(code="FINAL_EXAM_EVENT", active=True)
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_SPECIAL 쿠폰 타입을 찾을 수 없습니다."))
            return
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_EVENT 캠페인을 찾을 수 없습니다."))
            return
        
        # FINAL_EXAM_EVENT 캠페인을 사용하지만 잘못된 쿠폰 타입을 가진 쿠폰 찾기
        wrong_coupons = Coupon.objects.using(alias).filter(
            campaign=final_exam_camp
        ).exclude(
            coupon_type=final_exam_ct
        )
        
        wrong_count = wrong_coupons.count()
        
        if wrong_count == 0:
            self.stdout.write(self.style.SUCCESS("수정할 쿠폰이 없습니다. 모든 쿠폰이 올바른 타입입니다."))
            return
        
        # 잘못된 쿠폰 타입별 통계
        type_counts = wrong_coupons.values('coupon_type__code', 'coupon_type__title').annotate(
            count=__import__('django.db.models', fromlist=['Count']).Count('id')
        )
        
        self.stdout.write(f'\n=== 수정 예정 쿠폰 현황 ===')
        self.stdout.write(f'총 쿠폰 수: {wrong_count}개')
        self.stdout.write('\n잘못된 쿠폰 타입별 분포:')
        for item in type_counts:
            self.stdout.write(f'  {item["coupon_type__code"]} ({item["coupon_type__title"]}): {item["count"]}개')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] 실제로 수정하지 않습니다.'))
            return
        
        # 확인 메시지
        if not no_input:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {wrong_count}개의 쿠폰 타입을 수정합니다. 계속하시겠습니까?'))
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
                return
        
        # 실제 수정
        self.stdout.write('\n쿠폰 타입 수정 중...')
        
        with transaction.atomic(using=alias):
            updated = wrong_coupons.update(coupon_type=final_exam_ct)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 수정 완료 ===\n'
                f'수정된 쿠폰: {updated}개\n'
                f'쿠폰 타입: {final_exam_ct.title}'
            )
        )

