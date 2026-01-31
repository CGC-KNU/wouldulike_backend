from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q

from guests.models import GuestUser

User = get_user_model()


class Command(BaseCommand):
    help = "특정 UUID 또는 사용자 ID로 FCM 토큰 저장 상태를 확인합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            '--uuid',
            type=str,
            help='GuestUser의 UUID (예: b6760e94-70c8-444a-9aa5-19c729e35699)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User의 ID 또는 kakao_id',
        )
        parser.add_argument(
            '--kakao-id',
            type=int,
            help='User의 kakao_id',
        )
        parser.add_argument(
            '--token',
            type=str,
            help='확인할 FCM 토큰 (예: eQYL8BqINEHBj-Rc5Nbopw:APA91bHRPcQkvi7uV3...)',
        )
        parser.add_argument(
            '--check-overwrite',
            action='store_true',
            help='토큰 덮어쓰기 문제 확인 (같은 사용자의 여러 기기 확인)',
        )

    def handle(self, *args, **options):
        uuid = options.get('uuid')
        user_id = options.get('user_id')
        kakao_id = options.get('kakao_id')
        token = options.get('token')
        check_overwrite = options.get('check_overwrite', False)

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("FCM 토큰 저장 상태 확인")
        self.stdout.write("=" * 80 + "\n")

        # 1. UUID로 GuestUser 확인
        if uuid:
            self._check_guest_user_by_uuid(uuid, token)

        # 2. User ID 또는 kakao_id로 User 확인
        if user_id or kakao_id:
            self._check_user_by_id(user_id, kakao_id, token)

        # 3. 토큰으로 직접 검색
        if token:
            self._check_token_in_db(token)

        # 4. 토큰 덮어쓰기 문제 확인
        if check_overwrite:
            self._check_token_overwrite_issue()

    def _check_guest_user_by_uuid(self, uuid, expected_token=None):
        """UUID로 GuestUser의 토큰 확인"""
        self.stdout.write(f"📱 GuestUser UUID로 확인: {uuid}\n")

        try:
            guest_user = GuestUser.objects.get(uuid=uuid)
            
            self.stdout.write(f"✅ GuestUser 찾음:")
            self.stdout.write(f"   UUID: {guest_user.uuid}")
            self.stdout.write(f"   Type Code: {guest_user.type_code}")
            self.stdout.write(f"   FCM Token: {guest_user.fcm_token or '(없음)'}")
            self.stdout.write(f"   Created At: {guest_user.created_at}")
            self.stdout.write(f"   Updated At: {guest_user.updated_at}")
            
            if guest_user.linked_user:
                self.stdout.write(f"   Linked User: {guest_user.linked_user.kakao_id}")
                self.stdout.write(f"   Linked User FCM Token: {guest_user.linked_user.fcm_token or '(없음)'}")

            if expected_token:
                if guest_user.fcm_token == expected_token:
                    self.stdout.write(
                        self.style.SUCCESS(f"\n✅ 토큰 일치: 저장된 토큰이 예상한 토큰과 일치합니다.")
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"\n❌ 토큰 불일치:")
                    )
                    self.stdout.write(f"   예상 토큰: {expected_token[:50]}...")
                    self.stdout.write(f"   저장된 토큰: {guest_user.fcm_token[:50] if guest_user.fcm_token else '(없음)'}...")

        except GuestUser.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ UUID {uuid}에 해당하는 GuestUser를 찾을 수 없습니다.")
            )

    def _check_user_by_id(self, user_id, kakao_id, expected_token=None):
        """User ID 또는 kakao_id로 User의 토큰 확인"""
        if user_id:
            self.stdout.write(f"👤 User ID로 확인: {user_id}\n")
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ User ID {user_id}를 찾을 수 없습니다.")
                )
                return
        elif kakao_id:
            self.stdout.write(f"👤 kakao_id로 확인: {kakao_id}\n")
            try:
                user = User.objects.get(kakao_id=kakao_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ kakao_id {kakao_id}를 찾을 수 없습니다.")
                )
                return
        else:
            return

        self.stdout.write(f"✅ User 찾음:")
        self.stdout.write(f"   ID: {user.id}")
        self.stdout.write(f"   kakao_id: {user.kakao_id}")
        self.stdout.write(f"   FCM Token: {user.fcm_token or '(없음)'}")
        self.stdout.write(f"   Created At: {user.created_at}")
        self.stdout.write(f"   Updated At: {user.updated_at}")

        # 연결된 GuestUser 확인
        linked_guests = GuestUser.objects.filter(linked_user=user)
        if linked_guests.exists():
            self.stdout.write(f"\n   연결된 GuestUser: {linked_guests.count()}개")
            for guest in linked_guests:
                self.stdout.write(f"      - UUID: {guest.uuid}, Token: {guest.fcm_token or '(없음)'}")

        if expected_token:
            if user.fcm_token == expected_token:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ 토큰 일치: 저장된 토큰이 예상한 토큰과 일치합니다.")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"\n❌ 토큰 불일치:")
                )
                self.stdout.write(f"   예상 토큰: {expected_token[:50]}...")
                self.stdout.write(f"   저장된 토큰: {user.fcm_token[:50] if user.fcm_token else '(없음)'}...")

    def _check_token_in_db(self, token):
        """토큰으로 DB에서 검색"""
        self.stdout.write(f"\n🔍 토큰으로 검색: {token[:50]}...\n")

        # GuestUser에서 검색
        guest_users = GuestUser.objects.filter(fcm_token=token)
        if guest_users.exists():
            self.stdout.write(f"✅ GuestUser에서 발견: {guest_users.count()}개")
            for guest in guest_users:
                self.stdout.write(f"   - UUID: {guest.uuid}, Type: {guest.type_code}")
        else:
            self.stdout.write("❌ GuestUser에서 발견되지 않음")

        # User에서 검색
        users = User.objects.filter(fcm_token=token)
        if users.exists():
            self.stdout.write(f"\n✅ User에서 발견: {users.count()}개")
            for user in users:
                self.stdout.write(f"   - kakao_id: {user.kakao_id}, ID: {user.id}")
        else:
            self.stdout.write("❌ User에서 발견되지 않음")

    def _check_token_overwrite_issue(self):
        """토큰 덮어쓰기 문제 확인"""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("토큰 덮어쓰기 문제 확인")
        self.stdout.write("=" * 80 + "\n")

        # User 모델: 한 사용자당 하나의 토큰만 저장 가능
        self.stdout.write("\n📊 User 모델 분석:")
        self.stdout.write("   구조: 한 사용자당 하나의 fcm_token 필드만 존재")
        self.stdout.write("   문제: 여러 기기 사용 시 마지막 토큰만 저장됨\n")

        users_with_token = User.objects.exclude(fcm_token__isnull=True).exclude(fcm_token="")
        self.stdout.write(f"   토큰이 있는 User: {users_with_token.count()}개")

        # GuestUser 모델: 한 GuestUser당 하나의 토큰만 저장 가능
        self.stdout.write("\n📊 GuestUser 모델 분석:")
        self.stdout.write("   구조: 한 GuestUser당 하나의 fcm_token 필드만 존재")
        self.stdout.write("   문제: 여러 기기 사용 시 마지막 토큰만 저장됨\n")

        guests_with_token = GuestUser.objects.exclude(fcm_token__isnull=True).exclude(fcm_token="")
        self.stdout.write(f"   토큰이 있는 GuestUser: {guests_with_token.count()}개")

        # 연결된 사용자 확인
        self.stdout.write("\n📊 연결된 사용자 확인:")
        linked_users = User.objects.filter(guest_users__isnull=False).distinct()
        self.stdout.write(f"   GuestUser와 연결된 User: {linked_users.count()}개")

        for user in linked_users[:10]:  # 최대 10개만 표시
            guests = GuestUser.objects.filter(linked_user=user)
            if guests.count() > 1:
                self.stdout.write(f"\n   ⚠️  User {user.kakao_id}: {guests.count()}개의 GuestUser 연결됨")
                for guest in guests:
                    self.stdout.write(f"      - UUID: {guest.uuid}, Token: {guest.fcm_token or '(없음)'}")

        # 권장 사항
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("권장 사항")
        self.stdout.write("=" * 80 + "\n")
        self.stdout.write("현재 구조는 한 사용자당 하나의 토큰만 저장합니다.")
        self.stdout.write("여러 기기를 지원하려면:")
        self.stdout.write("1. UserDevice 같은 별도 테이블 생성")
        self.stdout.write("2. user_id, device_id, platform, fcm_token 저장")
        self.stdout.write("3. 발송 시 해당 유저의 모든 활성 토큰으로 발송")
        self.stdout.write("=" * 80 + "\n")















