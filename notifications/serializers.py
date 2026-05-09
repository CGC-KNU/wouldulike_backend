from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "dedupe_key",
            "content",
            "scheduled_time",
            "sent",
            "sent_at",
            "created_at",
            "updated_at",
        ]