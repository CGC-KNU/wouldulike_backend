from rest_framework import serializers
from .models import PopupCampaign, Trend

class TrendSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Trend
        fields = ['id', 'title', 'description', 'image_url', 'blog_link', 'created_at', 'updated_at']

    def get_image_url(self, obj):
        # 절대 URL 반환
        if obj.image:
            # S3 URL이 이미 절대 경로로 저장되었으므로 직접 반환
            return obj.image.name if obj.image.name.startswith('http') else f'{obj.image.url}'
        return None


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
