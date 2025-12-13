from django.core.management.base import BaseCommand
from django.db import transaction, router
from coupons.models import Coupon, CouponType, Campaign
from coupons.service import _build_benefit_snapshot


class Command(BaseCommand):
    help = "기말고사 쿠폰의 benefit_snapshot을 업데이트하여 올바른 쿠폰 타입 제목을 표시하도록 합니다."

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
        
        # FINAL_EXAM_EVENT 캠페인을 사용하는 모든 쿠폰 찾기
        coupons = Coupon.objects.using(alias).filter(
            campaign=final_exam_camp
        )
        
        total_count = coupons.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("수정할 쿠폰이 없습니다."))
            return
        
        # benefit_snapshot이 없거나 잘못된 coupon_type_title을 가진 쿠폰 찾기
        wrong_snapshots = []
        for coupon in coupons:
            snapshot = coupon.benefit_snapshot or {}
            snapshot_title = snapshot.get("coupon_type_title", "")
            actual_title = coupon.coupon_type.title
            
            # benefit_snapshot이 없거나 coupon_type_title이 잘못된 경우
            # 또는 coupon_type_title이 없고 title만 있는 경우 (RestaurantCouponBenefit에서 복사된 경우)
            if not snapshot or snapshot_title != actual_title or (snapshot_title == "" and "title" in snapshot):
                wrong_snapshots.append(coupon)
        
        wrong_count = len(wrong_snapshots)
        
        if wrong_count == 0:
            self.stdout.write(self.style.SUCCESS("모든 쿠폰의 benefit_snapshot이 올바릅니다."))
            return
        
        self.stdout.write(f'\n=== 수정 예정 쿠폰 현황 ===')
        self.stdout.write(f'총 쿠폰 수: {total_count}개')
        self.stdout.write(f'수정 필요한 쿠폰: {wrong_count}개')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] 실제로 수정하지 않습니다.'))
            return
        
        # 확인 메시지
        if not no_input:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {wrong_count}개의 쿠폰 benefit_snapshot을 업데이트합니다. 계속하시겠습니까?'))
            confirm = input('계속하려면 "yes"를 입력하세요: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
                return
        
        # 실제 수정
        self.stdout.write('\nbenefit_snapshot 업데이트 중...')
        
        updated_count = 0
        with transaction.atomic(using=alias):
            for coupon in wrong_snapshots:
                # benefit_snapshot 재생성
                if coupon.restaurant_id:
                    new_snapshot = _build_benefit_snapshot(
                        coupon.coupon_type,
                        coupon.restaurant_id,
                        db_alias=alias
                    )
                    coupon.benefit_snapshot = new_snapshot
                    coupon.save(update_fields=["benefit_snapshot"], using=alias)
                    updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 업데이트 완료 ===\n'
                f'업데이트된 쿠폰: {updated_count}개\n'
                f'쿠폰 타입 제목: {final_exam_ct.title}'
            )
        )

