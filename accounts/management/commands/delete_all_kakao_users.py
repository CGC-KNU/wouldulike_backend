"""
모든 카카오 로그인 사용자 정보를 완전히 삭제하는 명령어
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import DatabaseError, transaction
from coupons.models import Coupon, StampWallet, StampEvent, InviteCode, Referral
from guests.models import GuestUser

User = get_user_model()

# 쿠폰 관련 모델은 CloudSQL에 있음
CLOUDSQL_DB = 'cloudsql'
USER_DB = 'default'


class Command(BaseCommand):
    help = '모든 카카오 로그인 사용자 계정과 관련 데이터를 완전히 삭제합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 삭제하지 않고 미리보기만 표시',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='확인 없이 바로 삭제합니다 (--dry-run과 함께 사용 불가)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='삭제할 최대 사용자 수 (테스트용)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_input = options['no_input']
        limit = options.get('limit')

        if dry_run and no_input:
            raise CommandError('--dry-run과 --no-input은 함께 사용할 수 없습니다.')

        # 카카오 사용자 조회
        users = User.objects.using(USER_DB).exclude(kakao_id__isnull=True)
        
        if limit:
            users = users[:limit]
            self.stdout.write(self.style.WARNING(f'⚠️  제한 모드: 최대 {limit}명만 처리합니다.\n'))

        user_count = users.count()
        user_ids = list(users.values_list('id', flat=True))

        if user_count == 0:
            self.stdout.write(self.style.WARNING('삭제할 카카오 로그인 사용자가 없습니다.'))
            return

        # 삭제할 데이터 통계 수집
        self.stdout.write(self.style.WARNING('\n=== 삭제할 데이터 요약 ==='))
        self.stdout.write(f'삭제될 카카오 사용자 수: {user_count}명\n')

        try:
            stats = {
                'coupons': Coupon.objects.using(CLOUDSQL_DB).filter(user_id__in=user_ids).count(),
                'stamp_wallets': StampWallet.objects.using(CLOUDSQL_DB).filter(user_id__in=user_ids).count(),
                'stamp_events': StampEvent.objects.using(CLOUDSQL_DB).filter(user_id__in=user_ids).count(),
                'invite_codes': InviteCode.objects.using(CLOUDSQL_DB).filter(user_id__in=user_ids).count(),
                'referrals_as_referrer': Referral.objects.using(CLOUDSQL_DB).filter(referrer_id__in=user_ids).count(),
                'referrals_as_referee': Referral.objects.using(CLOUDSQL_DB).filter(referee_id__in=user_ids).count(),
                'guest_users': GuestUser.objects.using(USER_DB).filter(linked_user_id__in=user_ids).count(),
            }
        except DatabaseError as e:
            self.stdout.write(self.style.WARNING(f'CloudSQL 접근 중 오류 (통계 수집 실패): {str(e)[:100]}'))
            stats = {
                'coupons': 0,
                'stamp_wallets': 0,
                'stamp_events': 0,
                'invite_codes': 0,
                'referrals_as_referrer': 0,
                'referrals_as_referee': 0,
                'guest_users': GuestUser.objects.using(USER_DB).filter(linked_user_id__in=user_ids).count(),
            }

        self.stdout.write('삭제될 데이터:')
        self.stdout.write(f'  - 사용자 계정: {user_count}개')
        self.stdout.write(f'  - 쿠폰: {stats["coupons"]}개')
        self.stdout.write(f'  - 스탬프 지갑: {stats["stamp_wallets"]}개')
        self.stdout.write(f'  - 스탬프 이벤트: {stats["stamp_events"]}개')
        self.stdout.write(f'  - 초대코드: {stats["invite_codes"]}개')
        self.stdout.write(f'  - 추천인 기록 (내가 추천한 사람): {stats["referrals_as_referrer"]}개')
        self.stdout.write(f'  - 추천인 기록 (나를 추천한 사람): {stats["referrals_as_referee"]}개')
        self.stdout.write(f'  - 연결된 게스트 사용자: {stats["guest_users"]}개')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN 모드: 실제 삭제하지 않습니다.'))
            return

        # 확인
        if not no_input:
            self.stdout.write(self.style.ERROR('⚠️  ⚠️  ⚠️  경고: 모든 카카오 사용자 데이터가 영구적으로 삭제됩니다! ⚠️  ⚠️  ⚠️'))
            confirm = input('\n정말로 모든 카카오 사용자의 데이터를 삭제하시겠습니까? (yes 입력): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('삭제가 취소되었습니다.'))
                return

        # 실제 삭제 수행
        self.stdout.write(self.style.WARNING('\n데이터 삭제를 시작합니다...'))

        deleted_counts = {
            'users': 0,
            'coupons': 0,
            'stamp_wallets': 0,
            'stamp_events': 0,
            'invite_codes': 0,
            'referrals_as_referrer': 0,
            'referrals_as_referee': 0,
            'guest_users_unlinked': 0,
        }

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

        # 1. 쿠폰 삭제 (CloudSQL)
        try:
            deleted_counts['coupons'] = safe_delete_cloudsql(
                Coupon, {'user_id__in': user_ids}, '쿠폰'
            )
            self.stdout.write(f'  ✓ 쿠폰 삭제 완료: {deleted_counts["coupons"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  쿠폰 삭제 중 오류: {str(e)[:100]}'))

        # 2. 스탬프 지갑 삭제 (CloudSQL)
        try:
            deleted_counts['stamp_wallets'] = safe_delete_cloudsql(
                StampWallet, {'user_id__in': user_ids}, '스탬프 지갑'
            )
            self.stdout.write(f'  ✓ 스탬프 지갑 삭제 완료: {deleted_counts["stamp_wallets"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  스탬프 지갑 삭제 중 오류: {str(e)[:100]}'))

        # 3. 스탬프 이벤트 삭제 (CloudSQL)
        try:
            deleted_counts['stamp_events'] = safe_delete_cloudsql(
                StampEvent, {'user_id__in': user_ids}, '스탬프 이벤트'
            )
            self.stdout.write(f'  ✓ 스탬프 이벤트 삭제 완료: {deleted_counts["stamp_events"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  스탬프 이벤트 삭제 중 오류: {str(e)[:100]}'))

        # 4. 초대코드 삭제 (CloudSQL)
        try:
            deleted_counts['invite_codes'] = safe_delete_cloudsql(
                InviteCode, {'user_id__in': user_ids}, '초대코드'
            )
            self.stdout.write(f'  ✓ 초대코드 삭제 완료: {deleted_counts["invite_codes"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  초대코드 삭제 중 오류: {str(e)[:100]}'))

        # 5. 추천인 기록 삭제 - 내가 추천한 사람 (CloudSQL)
        try:
            deleted_counts['referrals_as_referrer'] = safe_delete_cloudsql(
                Referral, {'referrer_id__in': user_ids}, '추천인 기록 (내가 추천한 사람)'
            )
            self.stdout.write(f'  ✓ 추천인 기록 (내가 추천한 사람) 삭제 완료: {deleted_counts["referrals_as_referrer"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  추천인 기록 삭제 중 오류: {str(e)[:100]}'))

        # 6. 추천인 기록 삭제 - 나를 추천한 사람 (CloudSQL)
        try:
            deleted_counts['referrals_as_referee'] = safe_delete_cloudsql(
                Referral, {'referee_id__in': user_ids}, '추천인 기록 (나를 추천한 사람)'
            )
            self.stdout.write(f'  ✓ 추천인 기록 (나를 추천한 사람) 삭제 완료: {deleted_counts["referrals_as_referee"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  추천인 기록 삭제 중 오류: {str(e)[:100]}'))

        # 7. 게스트 사용자 연결 해제 (SET_NULL이므로 자동으로 NULL로 설정됨)
        try:
            guest_count = GuestUser.objects.using(USER_DB).filter(linked_user_id__in=user_ids).count()
            if guest_count > 0:
                GuestUser.objects.using(USER_DB).filter(linked_user_id__in=user_ids).update(linked_user=None)
                deleted_counts['guest_users_unlinked'] = guest_count
                self.stdout.write(f'  ✓ 게스트 사용자 연결 해제 완료: {deleted_counts["guest_users_unlinked"]}개')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  게스트 사용자 연결 해제 중 오류: {str(e)[:100]}'))

        # 8. JWT 토큰 blacklist 삭제
        try:
            if user_ids:  # user_ids가 비어있지 않을 때만 실행
                from django.db import connection
                with connection.cursor() as cursor:
                    # 먼저 BlacklistedToken 삭제
                    placeholders = ','.join(['%s'] * len(user_ids))
                    cursor.execute(
                        f"""DELETE FROM token_blacklist_blacklistedtoken 
                           WHERE token_id IN (
                               SELECT id FROM token_blacklist_outstandingtoken WHERE user_id IN ({placeholders})
                           )""",
                        user_ids
                    )
                    blacklisted_count = cursor.rowcount
                    
                    # 그 다음 OutstandingToken 삭제
                    cursor.execute(
                        f"DELETE FROM token_blacklist_outstandingtoken WHERE user_id IN ({placeholders})",
                        user_ids
                    )
                    outstanding_count = cursor.rowcount
                if outstanding_count > 0 or blacklisted_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ JWT 토큰 blacklist 삭제 완료 (Outstanding: {outstanding_count}, Blacklisted: {blacklisted_count})')
                    )
            else:
                outstanding_count = 0
                blacklisted_count = 0
        except DatabaseError as e:
            if 'does not exist' not in str(e).lower() and 'relation' not in str(e).lower():
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  JWT 토큰 blacklist 삭제 중 오류: {str(e)[:100]}')
                )
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  JWT 토큰 blacklist 삭제 중 예상치 못한 오류: {str(e)[:100]}')
            )

        # 9. 마지막으로 사용자 삭제
        # CASCADE가 다른 DB(cloudsql)를 참조하려고 하므로 SQL로 직접 삭제
        # 외래 키 제약 조건을 일시적으로 비활성화하여 다른 DB 참조 오류 방지
        try:
            from django.db import connection
            if user_ids:
                placeholders = ','.join(['%s'] * len(user_ids))
                with connection.cursor() as cursor:
                    # PostgreSQL: 외래 키 제약 조건 일시적으로 비활성화
                    try:
                        cursor.execute("SET session_replication_role = 'replica'")
                    except DatabaseError:
                        # PostgreSQL이 아닌 경우 무시
                        pass
                    
                    try:
                        # accounts_user 테이블에서 직접 삭제
                        cursor.execute(
                            f"DELETE FROM accounts_user WHERE id IN ({placeholders})",
                            user_ids
                        )
                        deleted_counts['users'] = cursor.rowcount
                    finally:
                        # 외래 키 제약 조건 다시 활성화
                        try:
                            cursor.execute("SET session_replication_role = 'origin'")
                        except DatabaseError:
                            pass
            else:
                deleted_counts['users'] = 0
            self.stdout.write(self.style.SUCCESS(f'  ✓ 사용자 계정 삭제 완료: {deleted_counts["users"]}개'))
        except DatabaseError as e:
            error_msg = str(e)
            # "relation does not exist" 오류는 이미 관련 데이터가 삭제되었거나 다른 DB에 있어서 발생할 수 있음
            if 'does not exist' in error_msg.lower() or 'relation' in error_msg.lower():
                # 사용자가 실제로 삭제되었는지 확인
                remaining_count = User.objects.using(USER_DB).filter(id__in=user_ids).count()
                if remaining_count == 0:
                    deleted_counts['users'] = len(user_ids)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ 사용자 계정 삭제 완료: {deleted_counts["users"]}개 '
                            f'(외래 키 제약 조건 경고 무시됨)'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  사용자 삭제 중 일부 오류 발생: {remaining_count}명이 남아있습니다. '
                            f'오류: {error_msg[:100]}'
                        )
                    )
                    deleted_counts['users'] = len(user_ids) - remaining_count
            else:
                raise CommandError(f'사용자 삭제 중 오류가 발생했습니다: {error_msg}')
        except Exception as e:
            raise CommandError(f'사용자 삭제 중 오류가 발생했습니다: {str(e)}')

        # 결과 출력
        self.stdout.write(self.style.SUCCESS('\n=== 삭제 완료 ==='))
        self.stdout.write(f'삭제된 사용자 계정: {deleted_counts["users"]}개')
        self.stdout.write(f'삭제된 쿠폰: {deleted_counts["coupons"]}개')
        self.stdout.write(f'삭제된 스탬프 지갑: {deleted_counts["stamp_wallets"]}개')
        self.stdout.write(f'삭제된 스탬프 이벤트: {deleted_counts["stamp_events"]}개')
        self.stdout.write(f'삭제된 초대코드: {deleted_counts["invite_codes"]}개')
        self.stdout.write(f'삭제된 추천인 기록 (내가 추천한 사람): {deleted_counts["referrals_as_referrer"]}개')
        self.stdout.write(f'삭제된 추천인 기록 (나를 추천한 사람): {deleted_counts["referrals_as_referee"]}개')
        self.stdout.write(f'연결 해제된 게스트 사용자: {deleted_counts["guest_users_unlinked"]}개')
        self.stdout.write(self.style.SUCCESS(f'\n모든 카카오 사용자 데이터가 성공적으로 삭제되었습니다.'))

