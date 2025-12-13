from django.core.management.base import BaseCommand
from django.db import router
from coupons.models import Coupon, CouponType, Campaign
from coupons.api.serializers import CouponSerializer
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

User = get_user_model()


class Command(BaseCommand):
    help = "특정 사용자의 쿠폰 API 응답 구조를 보여줍니다."

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
        ).select_related('coupon_type', 'campaign')[:5]  # 최대 5개만
        
        self.stdout.write(f'\n=== {campaign_code} 캠페인 쿠폰 API 응답 구조 ===')
        self.stdout.write(f'총 쿠폰 수: {coupons.count()}개\n')
        
        if coupons.exists():
            # API 요청 컨텍스트 생성
            factory = APIRequestFactory()
            request = factory.get('/api/coupons/my/')
            request.user = user
            
            serializer = CouponSerializer(coupons, many=True, context={'request': request})
            
            import json
            response_data = serializer.data
            
            self.stdout.write('=' * 80)
            self.stdout.write('API 응답 구조 (JSON 형식):')
            self.stdout.write('=' * 80)
            self.stdout.write(json.dumps(response_data, indent=2, ensure_ascii=False, default=str))
            
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write('각 쿠폰의 주요 필드:')
            self.stdout.write('=' * 80)
            
            for idx, coupon_data in enumerate(response_data, 1):
                self.stdout.write(f'\n[{idx}] 쿠폰 코드: {coupon_data.get("code")}')
                self.stdout.write(f'  - coupon_type (ID): {coupon_data.get("coupon_type")}')
                self.stdout.write(f'  - coupon_type_code: {coupon_data.get("coupon_type_code")}')
                self.stdout.write(f'  - coupon_type_title: {coupon_data.get("coupon_type_title")}')
                self.stdout.write(f'  - status: {coupon_data.get("status")}')
                self.stdout.write(f'  - restaurant_id: {coupon_data.get("restaurant_id")}')
                self.stdout.write(f'  - restaurant_name: {coupon_data.get("restaurant_name")}')
                
                benefit = coupon_data.get("benefit", {})
                if benefit:
                    self.stdout.write(f'  - benefit.coupon_type_code: {benefit.get("coupon_type_code")}')
                    self.stdout.write(f'  - benefit.coupon_type_title: {benefit.get("coupon_type_title")}')
                    self.stdout.write(f'  - benefit.title: {benefit.get("title")}')
                    self.stdout.write(f'  - benefit.subtitle: {benefit.get("subtitle")}')
                    self.stdout.write(f'  - benefit.restaurant_name: {benefit.get("restaurant_name")}')
        else:
            self.stdout.write(self.style.WARNING('해당 캠페인의 쿠폰이 없습니다.'))

