from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from coupons.models import Coupon, StampWallet, StampEvent, InviteCode, Referral
from guests.models import GuestUser

User = get_user_model()


class Command(BaseCommand):
    help = '특정 카카오 사용자 계정의 모든 데이터를 삭제합니다 (쿠폰, 스탬프, 초대코드 등)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--kakao-id',
            type=int,
            required=True,
            help='삭제할 사용자의 카카오 ID',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='확인 없이 바로 삭제합니다',
        )

    def handle(self, *args, **options):
        kakao_id = options['kakao_id']
        no_input = options['no_input']

        try:
            user = User.objects.get(kakao_id=kakao_id)
        except User.DoesNotExist:
            raise CommandError(f'카카오 ID {kakao_id}에 해당하는 사용자를 찾을 수 없습니다.')

        # 삭제할 데이터 통계 수집
        stats = {
            'coupons': user.coupons.count(),
            'stamp_wallets': user.stamp_wallets.count(),
            'stamp_events': user.stamp_events.count(),
            'invite_code': 1 if hasattr(user, 'invite_code') else 0,
            'referrals_made': user.referrals_made.count(),
            'referral_from': 1 if hasattr(user, 'referral_from') else 0,
            'guest_users': user.guest_users.count(),
        }

        # 삭제할 데이터 요약 출력
        self.stdout.write(self.style.WARNING('\n=== 삭제할 데이터 요약 ==='))
        self.stdout.write(f'사용자 ID: {user.id}')
        self.stdout.write(f'카카오 ID: {user.kakao_id}')
        self.stdout.write(f'생성일: {user.created_at}')
        self.stdout.write('')
        self.stdout.write('삭제될 데이터:')
        self.stdout.write(f'  - 쿠폰: {stats["coupons"]}개')
        self.stdout.write(f'  - 스탬프 지갑: {stats["stamp_wallets"]}개')
        self.stdout.write(f'  - 스탬프 이벤트: {stats["stamp_events"]}개')
        self.stdout.write(f'  - 초대코드: {stats["invite_code"]}개')
        self.stdout.write(f'  - 추천인 기록 (내가 추천한 사람): {stats["referrals_made"]}개')
        self.stdout.write(f'  - 추천인 기록 (나를 추천한 사람): {stats["referral_from"]}개')
        self.stdout.write(f'  - 연결된 게스트 사용자: {stats["guest_users"]}개')
        self.stdout.write('')

        # 확인
        if not no_input:
            confirm = input('정말로 이 사용자의 모든 데이터를 삭제하시겠습니까? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('삭제가 취소되었습니다.'))
                return

        # 실제 삭제 수행
        self.stdout.write(self.style.WARNING('데이터 삭제를 시작합니다...'))

        # CASCADE로 자동 삭제되지만, 명시적으로 삭제 통계를 보여주기 위해
        # 각 모델의 개수를 먼저 확인하고 삭제
        deleted_counts = {}

        # 쿠폰 삭제
        deleted_counts['coupons'] = user.coupons.count()
        user.coupons.all().delete()

        # 스탬프 지갑 삭제
        deleted_counts['stamp_wallets'] = user.stamp_wallets.count()
        user.stamp_wallets.all().delete()

        # 스탬프 이벤트 삭제
        deleted_counts['stamp_events'] = user.stamp_events.count()
        user.stamp_events.all().delete()

        # 초대코드 삭제 (OneToOne이므로 hasattr로 확인)
        if hasattr(user, 'invite_code'):
            user.invite_code.delete()
            deleted_counts['invite_code'] = 1
        else:
            deleted_counts['invite_code'] = 0

        # 추천인 기록 삭제 (내가 추천한 사람)
        deleted_counts['referrals_made'] = user.referrals_made.count()
        user.referrals_made.all().delete()

        # 추천인 기록 삭제 (나를 추천한 사람)
        if hasattr(user, 'referral_from'):
            user.referral_from.delete()
            deleted_counts['referral_from'] = 1
        else:
            deleted_counts['referral_from'] = 0

        # 게스트 사용자 연결 해제 (SET_NULL이므로 자동으로 NULL로 설정됨)
        deleted_counts['guest_users'] = user.guest_users.count()
        user.guest_users.update(linked_user=None)

        # 마지막으로 사용자 삭제
        user.delete()

        # 결과 출력
        self.stdout.write(self.style.SUCCESS('\n=== 삭제 완료 ==='))
        self.stdout.write(f'삭제된 쿠폰: {deleted_counts["coupons"]}개')
        self.stdout.write(f'삭제된 스탬프 지갑: {deleted_counts["stamp_wallets"]}개')
        self.stdout.write(f'삭제된 스탬프 이벤트: {deleted_counts["stamp_events"]}개')
        self.stdout.write(f'삭제된 초대코드: {deleted_counts["invite_code"]}개')
        self.stdout.write(f'삭제된 추천인 기록 (내가 추천한 사람): {deleted_counts["referrals_made"]}개')
        self.stdout.write(f'삭제된 추천인 기록 (나를 추천한 사람): {deleted_counts["referral_from"]}개')
        self.stdout.write(f'연결 해제된 게스트 사용자: {deleted_counts["guest_users"]}개')
        self.stdout.write(self.style.SUCCESS(f'\n카카오 ID {kakao_id}의 모든 데이터가 성공적으로 삭제되었습니다.'))

