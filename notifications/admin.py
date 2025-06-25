from django.contrib import admin
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['content', 'scheduled_time', 'created_at', 'updated_at']
    search_fields = ['content']