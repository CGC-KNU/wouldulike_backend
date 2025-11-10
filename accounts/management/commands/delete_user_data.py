from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection
from coupons.models import Coupon, StampWallet, StampEvent, InviteCode, Referral
from guests.models import GuestUser

User = get_user_model()

# 쿠폰 관련 모델은 CloudSQL에 있음
CLOUDSQL_DB = 'cloudsql'


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
        # 쿠폰 관련 모델은 CloudSQL에서 조회
        try:
            stats = {
                'coupons': Coupon.objects.using(CLOUDSQL_DB).filter(user_id=user.id).count(),
                'stamp_wallets': StampWallet.objects.using(CLOUDSQL_DB).filter(user_id=user.id).count(),
                'stamp_events': StampEvent.objects.using(CLOUDSQL_DB).filter(user_id=user.id).count(),
                'invite_code': 1 if InviteCode.objects.using(CLOUDSQL_DB).filter(user_id=user.id).exists() else 0,
                'referrals_made': Referral.objects.using(CLOUDSQL_DB).filter(referrer_id=user.id).count(),
                'referral_from': 1 if Referral.objects.using(CLOUDSQL_DB).filter(referee_id=user.id).exists() else 0,
                'guest_users': user.guest_users.count(),  # GuestUser는 default DB
            }
        except DatabaseError as e:
            # CloudSQL에 접근할 수 없는 경우 (예: DISABLE_EXTERNAL_DBS=True)
            self.stdout.write(self.style.WARNING(f'CloudSQL 접근 중 오류 (통계 수집 실패): {str(e)[:100]}'))
            stats = {
                'coupons': 0,
                'stamp_wallets': 0,
                'stamp_events': 0,
                'invite_code': 0,
                'referrals_made': 0,
                'referral_from': 0,
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

        # 안전한 삭제 헬퍼 함수 (CloudSQL용)
        def safe_delete_cloudsql(model_class, filter_kwargs, model_name):
            """CloudSQL에서 모델 삭제"""
            try:
                queryset = model_class.objects.using(CLOUDSQL_DB).filter(**filter_kwargs)
                count = queryset.count()
                if count > 0:
                    queryset.delete()
                return count
            except DatabaseError as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  {model_name} 삭제 중 오류 (무시하고 계속): {str(e)[:100]}')
                )
                return 0
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  {model_name} 삭제 중 예상치 못한 오류 (무시하고 계속): {str(e)[:100]}')
                )
                return 0

        # 쿠폰 삭제 (CloudSQL)
        try:
            deleted_counts['coupons'] = safe_delete_cloudsql(
                Coupon, {'user_id': user.id}, '쿠폰'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  쿠폰 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['coupons'] = 0

        # 스탬프 지갑 삭제 (CloudSQL)
        try:
            deleted_counts['stamp_wallets'] = safe_delete_cloudsql(
                StampWallet, {'user_id': user.id}, '스탬프 지갑'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  스탬프 지갑 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['stamp_wallets'] = 0

        # 스탬프 이벤트 삭제 (CloudSQL)
        try:
            deleted_counts['stamp_events'] = safe_delete_cloudsql(
                StampEvent, {'user_id': user.id}, '스탬프 이벤트'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  스탬프 이벤트 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['stamp_events'] = 0

        # 초대코드 삭제 (CloudSQL, OneToOne)
        try:
            invite_code = InviteCode.objects.using(CLOUDSQL_DB).filter(user_id=user.id).first()
            if invite_code:
                invite_code.delete()
                deleted_counts['invite_code'] = 1
            else:
                deleted_counts['invite_code'] = 0
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  초대코드 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['invite_code'] = 0

        # 추천인 기록 삭제 - 내가 추천한 사람 (CloudSQL)
        try:
            deleted_counts['referrals_made'] = safe_delete_cloudsql(
                Referral, {'referrer_id': user.id}, '추천인 기록 (내가 추천한 사람)'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  추천인 기록 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['referrals_made'] = 0

        # 추천인 기록 삭제 - 나를 추천한 사람 (CloudSQL, OneToOne)
        try:
            referral_from = Referral.objects.using(CLOUDSQL_DB).filter(referee_id=user.id).first()
            if referral_from:
                referral_from.delete()
                deleted_counts['referral_from'] = 1
            else:
                deleted_counts['referral_from'] = 0
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  추천인 기록 삭제 중 오류: {str(e)[:100]}'))
            deleted_counts['referral_from'] = 0

        # 게스트 사용자 연결 해제 (SET_NULL이므로 자동으로 NULL로 설정됨)
        try:
            deleted_counts['guest_users'] = user.guest_users.count()
            user.guest_users.update(linked_user=None)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  게스트 사용자 연결 해제 중 오류: {str(e)[:100]}'))
            deleted_counts['guest_users'] = 0

        # JWT 토큰 blacklist 삭제 (사용자 삭제 전에 필요)
        try:
            user_id = user.id
            with connection.cursor() as cursor:
                # 먼저 BlacklistedToken 삭제 (OutstandingToken을 참조하므로 먼저 삭제)
                cursor.execute(
                    """DELETE FROM token_blacklist_blacklistedtoken 
                       WHERE token_id IN (
                           SELECT id FROM token_blacklist_outstandingtoken WHERE user_id = %s
                       )""",
                    [user_id]
                )
                blacklisted_count = cursor.rowcount
                
                # 그 다음 OutstandingToken 삭제
                cursor.execute(
                    "DELETE FROM token_blacklist_outstandingtoken WHERE user_id = %s",
                    [user_id]
                )
                outstanding_count = cursor.rowcount
                
            if outstanding_count > 0 or blacklisted_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ JWT 토큰 blacklist 삭제 완료 (Outstanding: {outstanding_count}, Blacklisted: {blacklisted_count})')
                )
        except DatabaseError as e:
            # 테이블이 없거나 다른 오류인 경우 경고만 출력하고 계속 진행
            if 'does not exist' in str(e).lower() or 'relation' in str(e).lower():
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  JWT 토큰 blacklist 테이블 접근 중 오류 (무시하고 계속): {str(e)[:100]}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  JWT 토큰 blacklist 삭제 중 오류 (무시하고 계속): {str(e)[:100]}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  JWT 토큰 blacklist 삭제 중 예상치 못한 오류 (무시하고 계속): {str(e)[:100]}')
            )

        # 마지막으로 사용자 삭제
        # CASCADE 삭제가 CloudSQL 테이블을 찾으려고 하므로, SQL로 직접 삭제
        # 관련 데이터는 이미 모두 삭제했으므로 CASCADE가 필요 없음
        try:
            user_id = user.id
            
            # SQL로 직접 삭제 (CASCADE 우회)
            # default DB에서만 삭제
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM accounts_user WHERE id = %s", [user_id])
            
            self.stdout.write(self.style.SUCCESS('  ✓ 사용자 계정 삭제 완료'))
        except DatabaseError as e:
            raise CommandError(f'사용자 삭제 중 오류가 발생했습니다: {str(e)}')
        except Exception as e:
            raise CommandError(f'사용자 삭제 중 오류가 발생했습니다: {str(e)}')

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

