from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'nickname', 'student_id', 'department', 'school']


class AppleLoginSerializer(serializers.Serializer):
    """Apple 로그인 요청 검증"""

    identity_token = serializers.CharField(required=True, allow_blank=False)
    authorization_code = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    email = serializers.EmailField(required=False, allow_blank=True)