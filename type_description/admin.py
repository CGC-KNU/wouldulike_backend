from django.contrib import admin
from django.conf import settings

from .models import TypeDescription


if not getattr(settings, "USE_LOCAL_SQLITE", False):

    @admin.register(TypeDescription)
    class TypeDescriptionAdmin(admin.ModelAdmin):
        list_display = ("type_code", "type_name", "updated_at")
        search_fields = ("type_code", "type_name")
        readonly_fields = (
            "id",
            "type_code",
            "type_name",
            "description",
            "created_at",
            "updated_at",
            "description_detail",
            "menu_and_mbti",
            "meal_example",
            "matching_type",
            "non_matching_type",
            "type_summary",
        )

        def has_add_permission(self, request):
            return False

        def has_delete_permission(self, request, obj=None):
            return False

        def get_readonly_fields(self, request, obj=None):
            return self.readonly_fields

else:

    @admin.register(TypeDescription)
    class TypeDescriptionPlaceholderAdmin(admin.ModelAdmin):
        def has_module_permission(self, request):
            return False
