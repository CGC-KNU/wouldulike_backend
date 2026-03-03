from django.conf import settings
from rest_framework import serializers
from .models import PopupCampaign, Trend


class TrendSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Trend
        fields = ['id', 'title', 'description', 'image_url', 'blog_link', 'created_at', 'updated_at']

    def get_image_url(self, obj):
        """절대 URL 반환. S3 전체 URL 또는 상대 경로를 올바른 URL로 변환."""
        if not obj.image or not obj.image.name:
            return None
        name = obj.image.name
        # 이미 전체 URL로 저장된 경우 (http/https)
        if name.startswith(('http://', 'https://')):
            return name
        # 상대 경로인 경우: S3 도메인 또는 request 기반 절대 URL
        base_url = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None) or ''
        if base_url:
            if not base_url.endswith('/'):
                base_url += '/'
            return f'{base_url}{name}'
        # DEBUG 모드: request가 있으면 절대 URL 생성
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url


class PopupCampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = PopupCampaign
        fields = [
            "id",
            "title",
            "image_url",
            "instagram_url",
            "start_at",
            "end_at",
            "is_active",
            "display_order",
            "created_at",
            "updated_at",
        ]
