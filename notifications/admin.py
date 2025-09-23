from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("content", "scheduled_time", "sent", "created_at", "updated_at")
    list_filter = ("sent", "scheduled_time")
    search_fields = ("content",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-scheduled_time",)
