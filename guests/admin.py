from django.contrib import admin

from .models import GuestUser


@admin.register(GuestUser)
class GuestUserAdmin(admin.ModelAdmin):
    list_display = ("uuid", "type_code", "linked_user", "created_at", "updated_at")
    search_fields = ("uuid", "type_code", "linked_user__kakao_id")
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("type_code", "created_at")

    fieldsets = (
        (None, {"fields": ("uuid", "type_code", "favorite_restaurants", "linked_user")}),
        ("Notifications", {"fields": ("fcm_token",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
