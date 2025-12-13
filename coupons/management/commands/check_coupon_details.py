from django.core.management.base import BaseCommand
from django.db import router
from coupons.models import Coupon, CouponType, Campaign
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "특정 사용자의 쿠폰 상세 정보를 확인합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--kakao-id',
            type=int,
            help='카카오 ID로 사용자 지정',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID로 사용자 지정',
        )
        parser.add_argument(
            '--campaign',
            type=str,
            default='FINAL_EXAM_EVENT',
            help='캠페인 코드 (기본값: FINAL_EXAM_EVENT)',
        )

    def handle(self, *args, **options):
        kakao_id = options.get('kakao_id')
        user_id = options.get('user_id')
        campaign_code = options.get('campaign')
        
        alias = router.db_for_read(Coupon)
        
        # 사용자 찾기
        if kakao_id:
            try:
                user = User.objects.get(kakao_id=kakao_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"카카오 ID {kakao_id}에 해당하는 사용자를 찾을 수 없습니다."))
                return
        elif user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"User ID {user_id}에 해당하는 사용자를 찾을 수 없습니다."))
                return
        else:
            self.stdout.write(self.style.ERROR("--kakao-id 또는 --user-id를 지정해주세요."))
            return
        
        self.stdout.write(f'\n=== 사용자 정보 ===')
        self.stdout.write(f'User ID: {user.id}')
        self.stdout.write(f'Kakao ID: {user.kakao_id}')
        
        # 캠페인으로 쿠폰 찾기
        try:
            campaign = Campaign.objects.using(alias).get(code=campaign_code, active=True)
        except Campaign.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"캠페인 {campaign_code}을 찾을 수 없습니다."))
            return
        
        coupons = Coupon.objects.using(alias).filter(
            user=user,
            campaign=campaign
        ).select_related('coupon_type')
        
        self.stdout.write(f'\n=== {campaign_code} 캠페인 쿠폰 ===')
        self.stdout.write(f'총 쿠폰 수: {coupons.count()}개')
        
        if coupons.exists():
            for idx, coupon in enumerate(coupons[:10], 1):  # 최대 10개만 표시
                self.stdout.write(f'\n[{idx}] 쿠폰 코드: {coupon.code}')
                self.stdout.write(f'  - 쿠폰 타입 코드: {coupon.coupon_type.code}')
                self.stdout.write(f'  - 쿠폰 타입 제목: {coupon.coupon_type.title}')
                self.stdout.write(f'  - 상태: {coupon.status}')
                self.stdout.write(f'  - 식당 ID: {coupon.restaurant_id}')
                
                # benefit_snapshot 확인
                snapshot = coupon.benefit_snapshot or {}
                if snapshot:
                    self.stdout.write(f'  - benefit_snapshot coupon_type_title: {snapshot.get("coupon_type_title", "없음")}')
                    self.stdout.write(f'  - benefit_snapshot title: {snapshot.get("title", "없음")}')
                else:
                    self.stdout.write(f'  - benefit_snapshot: 없음')
        else:
            self.stdout.write(self.style.WARNING('해당 캠페인의 쿠폰이 없습니다.'))

