"""
관리자 로그인용 커스텀 인증 백엔드.
Username으로 조회 실패 시 카카오 ID(kakao_id)로도 시도.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class KakaoIdModelBackend(ModelBackend):
    """
    Username = 카카오 ID (문자열). 조회 실패 시 kakao_id로 재시도.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # 1) username으로 조회 (기본)
        user = User.objects.filter(username=username).first()
        if user is None and username.isdigit():
            # 2) kakao_id로 조회 시도
            user = User.objects.filter(kakao_id=int(username)).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
