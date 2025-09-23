from django.contrib import admin
from django.conf import settings

from .models import Restaurant


if not getattr(settings, "USE_LOCAL_SQLITE", False):

    @admin.register(Restaurant)
    class RestaurantAdmin(admin.ModelAdmin):
        list_display = ("id", "name", "status", "district_name", "phone_number", "liked_count")
        search_fields = ("name", "district_name", "phone_number")
        list_filter = ("status", "district_name")
        readonly_fields = (
            "id",
            "name",
            "status",
            "address_zip_code",
            "road_zip_code",
            "road_full_address",
            "road_address",
            "x",
            "y",
            "phone_number",
            "category_1",
            "category_2",
            "district_name",
            "attribute_1",
            "attribute_2",
            "attribute_3",
            "attribute_4",
            "liked_count",
        )

        def has_add_permission(self, request):
            return False

        def has_delete_permission(self, request, obj=None):
            return False

        def get_readonly_fields(self, request, obj=None):
            return self.readonly_fields

else:

    @admin.register(Restaurant)
    class RestaurantPlaceholderAdmin(admin.ModelAdmin):
        def has_module_permission(self, request):
            return False
