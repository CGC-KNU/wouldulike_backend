from rest_framework import serializers
from .models import Trend

class TrendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trend
        fields = ['id', 'title', 'description', 'image', 'blog_link', 'created_at', 'updated_at']
