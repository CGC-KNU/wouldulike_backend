from django.contrib import admin
from django import forms
from .models import GuestUser
import json

class GuestUserAdminForm(forms.ModelForm):
    class Meta:
        model = GuestUser
        fields = '__all__'

    def clean_favorite_restaurants(self):
        """쉼표로 구분된 문자열을 리스트로 변환 후 JSON으로 저장"""
        data = self.cleaned_data['favorite_restaurants']
        if data:
            return json.dumps([item.strip() for item in data.split(',') if item.strip()])
        return json.dumps([])

    def clean(self):
        """폼 유효성 검사를 추가로 정의 가능"""
        return super().clean()

class GuestUserAdmin(admin.ModelAdmin):
    form = GuestUserAdminForm
    list_display = ('uuid', 'type_code', 'display_favorite_restaurants', 'fcm_token', 'created_at')

    def display_favorite_restaurants(self, obj):
        """JSON 문자열을 리스트로 변환하여 표시"""
        return ", ".join(obj.get_favorite_restaurants())
    display_favorite_restaurants.short_description = '찜한 음식점'

admin.site.register(GuestUser, GuestUserAdmin)