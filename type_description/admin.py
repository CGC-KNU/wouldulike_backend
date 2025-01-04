from django.contrib import admin
from .models import TypeDescription

@admin.register(TypeDescription)
class TypeDescriptionAdmin(admin.ModelAdmin):
    list_display = ('type_code', 'description', 'created_at', 'updated_at')
    search_fields = ('type_code',)
