from unittest.mock import patch
from types import SimpleNamespace
import jwt
from django.test import override_settings
from rest_framework.test import APITestCase
from .models import User, SocialAccount
from guests.models import GuestUser
import uuid

KAKAO_RESPONSE = {
    'id': 12345,
    'kakao_account': {
        'email': 'jaemin@example.com',
        'profile': {
            'nickname': 'Jaemin',
            'profile_image_url': 'https://example.com/profile.jpg'
        }
    }
}


class DisableCouponSignalMixin:
    def setUp(self):
        super().setUp()
        self._coupon_patchers = [
            patch('coupons.signals.ensure_invite_code', return_value=None),
            patch('coupons.signals.issue_signup_coupon', return_value=None),
            patch('accounts.views.issue_signup_coupon', side_effect=lambda *args, **kwargs: SimpleNamespace(code='TESTCODE')),
        ]
        for patcher in self._coupon_patchers:
            patcher.start()
            self.addCleanup(patcher.stop)


class KakaoLoginTests(DisableCouponSignalMixin, APITestCase):
    @patch('accounts.views.requests.get')
    def test_new_user_login(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = KAKAO_RESPONSE
        response = self.client.post('/api/auth/kakao', {'access_token': 'valid'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_new'])
        self.assertEqual(User.objects.count(), 1)

    @patch('accounts.views.requests.get')
    def test_existing_user_login(self, mock_get):
        User.objects.create_user(kakao_id=12345)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = KAKAO_RESPONSE
        response = self.client.post('/api/auth/kakao', {'access_token': 'valid'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_new'])
        self.assertEqual(User.objects.count(), 1)

    @patch('accounts.views.requests.get')
    def test_invalid_token(self, mock_get):
        mock_get.return_value.status_code = 401
        response = self.client.post('/api/auth/kakao', {'access_token': 'bad'})
        self.assertEqual(response.status_code, 401)

    @patch('accounts.views.requests.get')
    def test_guest_merge(self, mock_get):
        guest = GuestUser.objects.create(type_code='AAAA')
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = KAKAO_RESPONSE
        response = self.client.post('/api/auth/kakao', {
            'access_token': 'valid',
            'guest_uuid': str(guest.uuid)
        })
        self.assertEqual(response.status_code, 200)
        user = User.objects.get()
        self.assertEqual(user.type_code, 'AAAA')

        guest.refresh_from_db()
        self.assertEqual(GuestUser.objects.count(), 1)
        self.assertEqual(guest.linked_user, user)
        self.assertEqual(guest.type_code, 'AAAA')

    @patch('accounts.views.requests.get')
    def test_guest_merge_overwrites_existing_type_code(self, mock_get):
        existing_user = User.objects.create_user(kakao_id=12345, type_code='BBBB')
        guest = GuestUser.objects.create(type_code='AAAA')
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = KAKAO_RESPONSE

        response = self.client.post('/api/auth/kakao', {
            'access_token': 'valid',
            'guest_uuid': str(guest.uuid)
        })

        self.assertEqual(response.status_code, 200)
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.type_code, 'AAAA')

        guest.refresh_from_db()
        self.assertEqual(GuestUser.objects.count(), 1)
        self.assertEqual(guest.linked_user, existing_user)
        self.assertEqual(guest.type_code, 'AAAA')

    @patch('accounts.views.requests.get')
    def test_guest_data_backfills_missing_fields(self, mock_get):
        existing_user = User.objects.create_user(
            kakao_id=12345,
            type_code='COOL',
            favorite_restaurants='["A"]',
            fcm_token='token-123',
        )
        guest = GuestUser.objects.create(type_code=None, favorite_restaurants=None, fcm_token=None)

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = KAKAO_RESPONSE

        response = self.client.post('/api/auth/kakao', {
            'access_token': 'valid',
            'guest_uuid': str(guest.uuid)
        })

        self.assertEqual(response.status_code, 200)

        existing_user.refresh_from_db()
        guest.refresh_from_db()

        self.assertEqual(existing_user.type_code, 'COOL')
        self.assertEqual(guest.type_code, 'COOL')
        self.assertEqual(guest.favorite_restaurants, '["A"]')
        self.assertEqual(guest.fcm_token, 'token-123')


class UserMeTests(DisableCouponSignalMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(kakao_id=54321, type_code='WARM')

    def authenticate(self):
        self.client.force_authenticate(user=self.user)

    def test_get_returns_current_type_code(self):
        self.authenticate()
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['type_code'], 'WARM')

    def test_patch_updates_type_code(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'type_code': 'COOL'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.type_code, 'COOL')

    def test_patch_rejects_invalid_type_code(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'type_code': 'INVALID'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.data)

    def test_patch_updates_favorite_restaurants(self):
        self.authenticate()
        payload = {'favorite_restaurants': ['A Restaurant']}
        response = self.client.patch('/api/users/me/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['favorite_restaurants'], ['A Restaurant'])
        self.user.refresh_from_db()
        self.assertIsInstance(self.user.favorite_restaurants, str)

    def test_put_behaves_like_patch(self):
        self.authenticate()
        response = self.client.put('/api/users/me/', {'type_code': 'MILD'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.type_code, 'MILD')

    def test_patch_rejects_nickname_with_spaces(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'nickname': 'jae min'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'nickname_invalid_format')

    def test_patch_rejects_nickname_with_special_chars(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'nickname': 'jaemin!'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'nickname_invalid_format')

    def test_patch_rejects_nickname_too_long(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'nickname': 'a' * 16}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'nickname_too_long')

    def test_patch_rejects_duplicated_nickname_case_insensitive(self):
        User.objects.create_user(kakao_id=99999, nickname='Jaemin')
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'nickname': 'jaemin'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data.get('code'), 'nickname_duplicated')

    def test_patch_updates_profile_codes(self):
        self.authenticate()
        payload = {
            'school_code': 'knu',
            'college_code': 'eng',
            'department_code': 'cse',
        }
        response = self.client.patch('/api/users/me/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['school_code'], 'KNU')
        self.assertEqual(response.data['college_code'], 'ENG')
        self.assertEqual(response.data['department_code'], 'CSE')

    def test_patch_rejects_invalid_profile_code(self):
        self.authenticate()
        response = self.client.patch('/api/users/me/', {'school_code': 'KNU-1'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'invalid_profile_code')


class NicknameAvailabilityTests(DisableCouponSignalMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(kakao_id=11111)
        self.client.force_authenticate(user=self.user)

    def test_nickname_availability_returns_false_when_duplicated(self):
        User.objects.create_user(kakao_id=22222, nickname='Tester')
        response = self.client.get('/api/users/nickname-availability?nickname=tester')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['available'])
        self.assertEqual(response.data['code'], 'nickname_duplicated')

    def test_nickname_availability_rejects_invalid_format(self):
        response = self.client.get('/api/users/nickname-availability?nickname=test er')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'nickname_invalid_format')

    def test_nickname_availability_rejects_nickname_too_long(self):
        response = self.client.get(f"/api/users/nickname-availability?nickname={'a' * 16}")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('code'), 'nickname_too_long')

    def test_nickname_availability_with_slash_path(self):
        response = self.client.get('/api/users/nickname-availability/?nickname=tester2')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['available'])


class AppleAuthServiceTests(APITestCase):
    """Apple identity_token 검증 서비스 단위 테스트"""

    @override_settings(APPLE_AUDIENCE=None)
    def test_verify_identity_token_missing_audience(self):
        """APPLE_AUDIENCE 미설정 시 ValueError"""
        from accounts.services.apple_auth import verify_identity_token
        with self.assertRaises(ValueError) as ctx:
            verify_identity_token('any.token.here', audience=None)
        self.assertIn('APPLE_AUDIENCE', str(ctx.exception))

    @override_settings(APPLE_AUDIENCE='com.example.app')
    def test_verify_identity_token_invalid_jwt(self):
        """잘못된 JWT 형식 시 InvalidTokenError"""
        from accounts.services.apple_auth import verify_identity_token
        with self.assertRaises(jwt.DecodeError):
            verify_identity_token('invalid.jwt.string', audience='com.example.app')


class AppleLoginTests(DisableCouponSignalMixin, APITestCase):
    """Apple 로그인 엔드포인트 통합 테스트"""

    VALID_CLAIMS = {
        'sub': '001234.abc123def456.7890',
        'email': 'user@privaterelay.appleid.com',
        'email_verified': 'true',
    }

    @patch('accounts.views.verify_identity_token')
    def test_apple_login_new_user(self, mock_verify):
        mock_verify.return_value = self.VALID_CLAIMS
        response = self.client.post(
            '/api/auth/apple/login/',
            {'identity_token': 'valid.jwt.here'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_new'])
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['apple_id'], self.VALID_CLAIMS['sub'])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.filter(provider='apple').count(), 1)

    @patch('accounts.views.verify_identity_token')
    def test_apple_login_existing_user(self, mock_verify):
        user = User.objects.create_user(apple_id=self.VALID_CLAIMS['sub'])
        SocialAccount.objects.create(
            provider='apple',
            provider_user_id=self.VALID_CLAIMS['sub'],
            user=user,
            email=self.VALID_CLAIMS['email'],
        )
        mock_verify.return_value = self.VALID_CLAIMS
        response = self.client.post(
            '/api/auth/apple/login/',
            {'identity_token': 'valid.jwt.here'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_new'])
        self.assertEqual(response.data['user']['id'], user.id)
        self.assertEqual(User.objects.count(), 1)

    @patch('accounts.views.verify_identity_token')
    def test_apple_login_invalid_token_returns_401(self, mock_verify):
        mock_verify.side_effect = jwt.InvalidTokenError('invalid')
        response = self.client.post(
            '/api/auth/apple/login/',
            {'identity_token': 'bad.token'},
            format='json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data.get('code'), 'apple_token_invalid')

    @patch('accounts.views.verify_identity_token')
    def test_apple_login_missing_identity_token_returns_400(self, mock_verify):
        response = self.client.post(
            '/api/auth/apple/login/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        mock_verify.assert_not_called()

    @patch('accounts.views.verify_identity_token')
    def test_apple_login_with_full_name_and_email(self, mock_verify):
        mock_verify.return_value = {'sub': '001234.xyz', 'email': None}
        response = self.client.post(
            '/api/auth/apple/login/',
            {
                'identity_token': 'valid.jwt',
                'full_name': 'John Doe',
                'email': 'john@example.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(apple_id='001234.xyz')
        self.assertEqual(user.nickname, 'John Doe')
        self.assertEqual(user.email, 'john@example.com')
