"""
앱 배포 후 초기 세팅을 위한 명령어

1. 카카오 로그인 사용자 목록 불러오기
2. 불러온 카카오 id 사용자들의 쿠폰, 스탬프 이력 초기화
3. 식당별 쿠폰 제한 200장 중 사용된것 초기화(다시 200장으로 세팅)
4. 식당별 pin 번호 새로 랜덤 생성
"""

import string
import secrets
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count

from restaurants.models import AffiliateRestaurant
from coupons.models import (
    Coupon,
    StampWallet,
    StampEvent,
    MerchantPin,
)

User = get_user_model()


class Command(BaseCommand):
    help = '앱 배포 후 초기 세팅: 사용자 쿠폰/스탬프 초기화, 식당 쿠폰 제한 초기화, PIN 번호 재생성'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 변경하지 않고 미리보기만 표시',
        )
        parser.add_argument(
            '--pin-length',
            type=int,
            default=4,
            help='생성할 PIN 번호 길이 (기본값: 4)',
        )
        parser.add_argument(
            '--step',
            type=int,
            choices=[1, 2, 3, 4],
            help='특정 단계만 실행 (1: 사용자 목록, 2: 사용자 데이터 초기화, 3: 쿠폰 제한 초기화, 4: PIN 재생성)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        pin_length = options['pin_length']
        step = options.get('step')
        user_db = 'default'  # User 모델은 default DB 사용
        coupon_db = 'cloudsql'  # Coupon, StampWallet, StampEvent는 cloudsql DB 사용

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY-RUN 모드: 실제 변경 없음 ===\n'))

        # 사용자 ID 리스트 초기화 (step 2나 3을 직접 실행할 때를 위해)
        user_ids = None

        # 1. 카카오 로그인 사용자 목록 불러오기
        if step is None or step == 1:
            self.stdout.write('1. 카카오 로그인 사용자 목록 조회 중...')
            kakao_users = User.objects.using(user_db).exclude(kakao_id__isnull=True)
            user_count = kakao_users.count()
            self.stdout.write(self.style.SUCCESS(f'   총 {user_count}명의 카카오 로그인 사용자 발견\n'))

            if user_count == 0:
                self.stdout.write(self.style.WARNING('카카오 로그인 사용자가 없습니다. 작업을 종료합니다.'))
                return

            # 사용자 목록 출력 (처음 10명만)
            self.stdout.write('   사용자 목록 (처음 10명):')
            for user in kakao_users[:10]:
                self.stdout.write(f'   - User ID: {user.id}, Kakao ID: {user.kakao_id}')
            if user_count > 10:
                self.stdout.write(f'   ... 외 {user_count - 10}명 더 있습니다.\n')
            else:
                self.stdout.write('')

            # 사용자 ID 리스트 추출 (다른 DB에서 사용하기 위해)
            user_ids = list(kakao_users.values_list('id', flat=True))

            if step == 1:
                self.stdout.write(self.style.SUCCESS('\n단계 1 완료: 사용자 목록 조회'))
                return

        # 2. 카카오 사용자들의 쿠폰, 스탬프 이력 초기화
        if step is None or step == 2:
            # user_ids가 없으면 먼저 조회
            if user_ids is None:
                kakao_users = User.objects.using(user_db).exclude(kakao_id__isnull=True)
                user_ids = list(kakao_users.values_list('id', flat=True))
                if not user_ids:
                    self.stdout.write(self.style.WARNING('카카오 로그인 사용자가 없습니다.'))
                    return
            self.stdout.write('2. 카카오 사용자들의 쿠폰, 스탬프 이력 초기화 중...')
            
            if not dry_run:
                # 쿠폰 삭제
                coupon_count = Coupon.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                Coupon.objects.using(coupon_db).filter(user_id__in=user_ids).delete()
                self.stdout.write(f'   - 삭제된 쿠폰: {coupon_count}개')
                
                # 스탬프 지갑 삭제
                wallet_count = StampWallet.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                StampWallet.objects.using(coupon_db).filter(user_id__in=user_ids).delete()
                self.stdout.write(f'   - 삭제된 스탬프 지갑: {wallet_count}개')
                
                # 스탬프 이벤트 삭제
                event_count = StampEvent.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                StampEvent.objects.using(coupon_db).filter(user_id__in=user_ids).delete()
                self.stdout.write(f'   - 삭제된 스탬프 이벤트: {event_count}개')
            else:
                coupon_count = Coupon.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                wallet_count = StampWallet.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                event_count = StampEvent.objects.using(coupon_db).filter(user_id__in=user_ids).count()
                self.stdout.write(f'   - 삭제될 쿠폰: {coupon_count}개')
                self.stdout.write(f'   - 삭제될 스탬프 지갑: {wallet_count}개')
                self.stdout.write(f'   - 삭제될 스탬프 이벤트: {event_count}개')
            
            self.stdout.write('')

            if step == 2:
                self.stdout.write(self.style.SUCCESS('\n단계 2 완료: 사용자 데이터 초기화'))
                return

        # 3. 식당별 쿠폰 제한 초기화 (REDEEMED 상태인 쿠폰 삭제)
        if step is None or step == 3:
            self.stdout.write('3. 식당별 쿠폰 제한 초기화 중 (REDEEMED 상태 쿠폰 삭제)...')
            
            if not dry_run:
                redeemed_count = Coupon.objects.using(coupon_db).filter(status='REDEEMED').count()
                Coupon.objects.using(coupon_db).filter(status='REDEEMED').delete()
                self.stdout.write(f'   - 삭제된 사용된 쿠폰: {redeemed_count}개')
                
                # 식당별 쿠폰 발급 현황 확인
                restaurant_coupon_counts = (
                    Coupon.objects.using(coupon_db)
                    .exclude(restaurant_id__isnull=True)
                    .values('restaurant_id')
                    .annotate(cnt=Count('id'))
                    .order_by('-cnt')
                )
                
                self.stdout.write('   식당별 남은 쿠폰 발급 수 (상위 10개):')
                for item in restaurant_coupon_counts[:10]:
                    self.stdout.write(f'   - Restaurant {item["restaurant_id"]}: {item["cnt"]}개')
            else:
                redeemed_count = Coupon.objects.using(coupon_db).filter(status='REDEEMED').count()
                self.stdout.write(f'   - 삭제될 사용된 쿠폰: {redeemed_count}개')
                
                restaurant_coupon_counts = (
                    Coupon.objects.using(coupon_db)
                    .exclude(restaurant_id__isnull=True)
                    .values('restaurant_id')
                    .annotate(cnt=Count('id'))
                    .order_by('-cnt')
                )
                
                self.stdout.write('   식당별 남은 쿠폰 발급 수 (상위 10개):')
                for item in restaurant_coupon_counts[:10]:
                    self.stdout.write(f'   - Restaurant {item["restaurant_id"]}: {item["cnt"]}개')
            
            self.stdout.write('')

            if step == 3:
                self.stdout.write(self.style.SUCCESS('\n단계 3 완료: 쿠폰 제한 초기화'))
                return

        # 4. 식당별 PIN 번호 새로 랜덤 생성
        if step is None or step == 4:
            self.stdout.write(f'4. 식당별 PIN 번호 새로 랜덤 생성 중 (길이: {pin_length})...')
            
            if pin_length < 4:
                self.stderr.write(self.style.ERROR('PIN 길이는 최소 4자리여야 합니다.'))
                return

            alphabet = string.digits
            created = updated = 0
            
            # 기존 PIN 수집 (중복 방지용)
            used = set(
                MerchantPin.objects.using(coupon_db)
                .exclude(secret__isnull=True)
                .values_list('secret', flat=True)
            )
            used.update(
                pin for pin in
                AffiliateRestaurant.objects.using(coupon_db)
                .exclude(pin_secret__isnull=True)
                .values_list('pin_secret', flat=True)
            )
            used.discard(None)

            def generate_unique():
                for _ in range(100):
                    candidate = ''.join(secrets.choice(alphabet) for _ in range(pin_length))
                    if candidate not in used:
                        used.add(candidate)
                        return candidate
                raise RuntimeError('고유한 PIN 생성 실패 (100회 시도 후)')

            restaurants = AffiliateRestaurant.objects.using(coupon_db).all()
            total = restaurants.count()
            self.stdout.write(f'   총 {total}개 식당 처리 중...')

            for restaurant in restaurants.iterator():
                mp = (
                    MerchantPin.objects.using(coupon_db)
                    .filter(restaurant_id=restaurant.restaurant_id)
                    .first()
                )

                new_pin = generate_unique()

                if dry_run:
                    action = '업데이트 예정' if mp else '생성 예정'
                    self.stdout.write(
                        f'   [{action}] restaurant_id={restaurant.restaurant_id} name={restaurant.name} pin={new_pin}'
                    )
                    continue

                now = timezone.now()
                with transaction.atomic(using=coupon_db):
                    obj, created_flag = MerchantPin.objects.using(coupon_db).update_or_create(
                        restaurant=restaurant,
                        defaults={
                            'algo': 'STATIC',
                            'secret': new_pin,
                            'period_sec': mp.period_sec if mp else 30,
                            'last_rotated_at': now,
                        },
                    )
                    AffiliateRestaurant.objects.using(coupon_db).filter(
                        restaurant_id=restaurant.restaurant_id
                    ).update(pin_secret=new_pin, pin_updated_at=now)

                if created_flag:
                    created += 1
                else:
                    updated += 1

            if dry_run:
                self.stdout.write(self.style.WARNING('\nDRY-RUN 모드: 실제 변경 없음'))
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n=== 초기화 완료 ===\n'
                    f'생성된 PIN: {created}개\n'
                    f'업데이트된 PIN: {updated}개'
                )
            )

