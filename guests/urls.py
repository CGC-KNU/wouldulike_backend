# guests/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('get-or-create-guest/', views.get_or_create_guest_user, name='get_or_create_guest'),
    path('update-preferences/', views.update_guest_preferences, name='update_preferences'),
    path('save-survey/', views.save_survey_response, name='save_survey_response'),
]
