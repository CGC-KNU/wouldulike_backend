from django.contrib import admin

from .models import PopupCampaign, Trend


@admin.register(Trend)
class TrendAdmin(admin.ModelAdmin):
    list_display = ("title", "blog_link", "created_at", "updated_at")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(PopupCampaign)
class PopupCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "display_order",
        "is_active",
        "start_at",
        "end_at",
        "created_at",
    )
    search_fields = ("title", "instagram_url")
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("display_order", "-created_at")
