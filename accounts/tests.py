from unittest.mock import patch
from types import SimpleNamespace
from rest_framework.test import APITestCase
from .models import User
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
