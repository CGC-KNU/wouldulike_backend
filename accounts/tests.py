from unittest.mock import patch
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


class KakaoLoginTests(APITestCase):
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
        self.assertEqual(GuestUser.objects.count(), 0)