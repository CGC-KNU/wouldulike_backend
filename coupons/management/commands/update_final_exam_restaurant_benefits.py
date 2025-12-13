from django.core.management.base import BaseCommand
from django.db import transaction, router
from coupons.models import CouponType, RestaurantCouponBenefit
from restaurants.models import AffiliateRestaurant


class Command(BaseCommand):
    help = "기말고사 쿠폰 타입(FINAL_EXAM_SPECIAL)의 RestaurantCouponBenefit title을 '기말고사 쪽지 이벤트'로 업데이트합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 수정하지 않고 수정될 항목 수만 확인합니다',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='확인 없이 바로 수정합니다',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_input = options['no_input']
        
        alias = router.db_for_write(RestaurantCouponBenefit)
        
        try:
            final_exam_ct = CouponType.objects.using(alias).get(code="FINAL_EXAM_SPECIAL")
        except CouponType.DoesNotExist:
            self.stdout.write(self.style.ERROR("FINAL_EXAM_SPECIAL 쿠폰 타입을 찾을 수 없습니다."))
            return
        
        # FINAL_EXAM_SPECIAL 쿠폰 타입의 모든 RestaurantCouponBenefit 찾기
        benefits = RestaurantCouponBenefit.objects.using(alias).filter(
            coupon_type=final_exam_ct
        )
        
        total_count = benefits.count()
        
        if total_count == 0:
            self.stdout.write(self.style.WARNING("FINAL_EXAM_SPECIAL 쿠폰 타입에 대한 RestaurantCouponBenefit이 없습니다."))
            self.stdout.write("먼저 마이그레이션을 실행하거나 수동으로 등록해주세요.")
            return
        
        # title이 "기말고사 쪽지 이벤트"가 아닌 항목 찾기
        wrong_title_benefits = benefits.exclude(title="기말고사 쪽지 이벤트")
        wrong_count = wrong_title_benefits.count()
        
        if wrong_count == 0:
            self.stdout.write(self.style.SUCCESS("모든 RestaurantCouponBenefit의 title이 올바릅니다."))
            return
        
        # 현재 title 분포 확인
        title_counts = benefits.values('title').annotate(
            count=__import__('django.db.models', fromlist=['Count']).Count('id')
        )
        
        self.stdout.write(f'\n=== 수정 예정 항목 현황 ===')
        self.stdout.write(f'총 RestaurantCouponBenefit 수: {total_count}개')
        self.stdout.write(f'수정 필요한 항목: {wrong_count}개')
        self.stdout.write('\n현재 title 분포:')
        for item in title_counts:
            self.stdout.write(f'  "{item["title"]}": {item["count"]}개')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] 실제로 수정하지 않습니다.'))
            return
        
        # 확인 메시지
        if not no_input:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {wrong_count}개의 RestaurantCouponBenefit title을 "기말고사 쪽지 이벤트"로 수정합니다. 계속하시겠습니까?'))
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
                return
        
        # 실제 수정
        self.stdout.write('\nRestaurantCouponBenefit title 업데이트 중...')
        
        updated_count = 0
        with transaction.atomic(using=alias):
            updated_count = wrong_title_benefits.update(title="기말고사 쪽지 이벤트")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 업데이트 완료 ===\n'
                f'업데이트된 항목: {updated_count}개\n'
                f'새로운 title: "기말고사 쪽지 이벤트"'
            )
        )
        
        self.stdout.write('\n주의: 이제 새로 발급되는 쿠폰의 benefit.title이 "기말고사 쪽지 이벤트"로 표시됩니다.')
        self.stdout.write('기존에 발급된 쿠폰의 benefit_snapshot을 업데이트하려면 다음 명령어를 실행하세요:')
        self.stdout.write('  python manage.py update_final_exam_benefit_snapshots')

