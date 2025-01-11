from django.contrib import admin
from .models import Trend

@admin.register(Trend)
class TrendAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'image', 'blog_link', 'created_at', 'updated_at']
    search_fields = ['title', 'description']
