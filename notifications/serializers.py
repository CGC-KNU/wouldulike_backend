from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'content', 'scheduled_time', 'sent', 'created_at', 'updated_at']