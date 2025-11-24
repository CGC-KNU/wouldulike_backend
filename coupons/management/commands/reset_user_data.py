"""
카카오 로그인 사용자들의 쿠폰, 스탬프 이력 초기화 명령어
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from coupons.models import Coupon, StampWallet, StampEvent

User = get_user_model()


class Command(BaseCommand):
    help = '카카오 로그인 사용자들의 쿠폰, 스탬프 이력 초기화'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 변경하지 않고 미리보기만 표시',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='특정 사용자 ID만 초기화 (선택사항)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options.get('user_id')
        user_db = 'default'  # User 모델은 default DB 사용
        coupon_db = 'cloudsql'  # Coupon, StampWallet, StampEvent는 cloudsql DB 사용

        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY-RUN 모드: 실제 변경 없음 ===\n'))

        # 사용자 쿼리 구성 (default DB 사용)
        if user_id:
            users = User.objects.using(user_db).filter(id=user_id, kakao_id__isnull=False)
            if not users.exists():
                self.stderr.write(self.style.ERROR(f'사용자 ID {user_id}를 찾을 수 없거나 카카오 로그인 사용자가 아닙니다.'))
                return
        else:
            users = User.objects.using(user_db).exclude(kakao_id__isnull=True)

        user_count = users.count()
        self.stdout.write(f'처리 대상 사용자: {user_count}명\n')

        if user_count == 0:
            self.stdout.write(self.style.WARNING('처리할 카카오 로그인 사용자가 없습니다.'))
            return

        # 사용자 ID 리스트 추출 (다른 DB에서 사용하기 위해)
        user_ids = list(users.values_list('id', flat=True))

        # 통계 수집 (cloudsql DB 사용)
        coupon_count = Coupon.objects.using(coupon_db).filter(user_id__in=user_ids).count()
        wallet_count = StampWallet.objects.using(coupon_db).filter(user_id__in=user_ids).count()
        event_count = StampEvent.objects.using(coupon_db).filter(user_id__in=user_ids).count()

        self.stdout.write('삭제될 데이터:')
        self.stdout.write(f'  - 쿠폰: {coupon_count}개')
        self.stdout.write(f'  - 스탬프 지갑: {wallet_count}개')
        self.stdout.write(f'  - 스탬프 이벤트: {event_count}개\n')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 모드: 실제 삭제하지 않습니다.'))
            return

        # 확인 메시지
        self.stdout.write(self.style.WARNING('⚠️  위 데이터를 모두 삭제합니다. 계속하시겠습니까?'))
        confirm = input('계속하려면 "yes"를 입력하세요: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('작업이 취소되었습니다.'))
            return

        # 실제 삭제
        self.stdout.write('\n데이터 삭제 중...')
        
        with transaction.atomic(using=coupon_db):
            deleted_coupons = Coupon.objects.using(coupon_db).filter(user_id__in=user_ids).delete()[0]
            deleted_wallets = StampWallet.objects.using(coupon_db).filter(user_id__in=user_ids).delete()[0]
            deleted_events = StampEvent.objects.using(coupon_db).filter(user_id__in=user_ids).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== 초기화 완료 ===\n'
                f'삭제된 쿠폰: {deleted_coupons}개\n'
                f'삭제된 스탬프 지갑: {deleted_wallets}개\n'
                f'삭제된 스탬프 이벤트: {deleted_events}개'
            )
        )

