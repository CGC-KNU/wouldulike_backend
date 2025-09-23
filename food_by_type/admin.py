from django.contrib import admin
from django.conf import settings

from .models import Food, TypeCode, TypeCodeFood


if not getattr(settings, "USE_LOCAL_SQLITE", False):

    class ReadOnlyAdmin(admin.ModelAdmin):
        def has_add_permission(self, request):
            return False

        def has_delete_permission(self, request, obj=None):
            return False

        def get_readonly_fields(self, request, obj=None):
            return [field.name for field in self.model._meta.fields]


    @admin.register(Food)
    class FoodAdmin(ReadOnlyAdmin):
        list_display = ("food_id", "food_name", "food_image_url")
        search_fields = ("food_name",)


    @admin.register(TypeCode)
    class TypeCodeAdmin(ReadOnlyAdmin):
        list_display = ("type_code_id", "type_code")
        search_fields = ("type_code",)


    @admin.register(TypeCodeFood)
    class TypeCodeFoodAdmin(ReadOnlyAdmin):
        list_display = ("type_code_id", "food_id")
        search_fields = ("type_code_id", "food_id")

else:

    @admin.register(Food)
    class FoodPlaceholderAdmin(admin.ModelAdmin):
        def has_module_permission(self, request):
            return False


    @admin.register(TypeCode)
    class TypeCodePlaceholderAdmin(admin.ModelAdmin):
        def has_module_permission(self, request):
            return False


    @admin.register(TypeCodeFood)
    class TypeCodeFoodPlaceholderAdmin(admin.ModelAdmin):
        def has_module_permission(self, request):
            return False
