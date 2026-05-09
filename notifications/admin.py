from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("dedupe_key", "content", "scheduled_time", "sent", "sent_at", "created_at", "updated_at")
    list_filter = ("sent", "scheduled_time")
    search_fields = ("dedupe_key", "content")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-scheduled_time",)
