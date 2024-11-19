# views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import GuestUser
import uuid

def get_or_create_guest_user(request):
    # 클라이언트에서 UUID를 전달받는다고 가정
    guest_uuid = request.COOKIES.get('guest_uuid')

    if guest_uuid:
        # UUID가 존재하면 데이터베이스에서 해당 사용자를 가져옵니다
        guest_user = get_object_or_404(GuestUser, uuid=guest_uuid)
    else:
        # UUID가 없으면 새로운 게스트 사용자를 생성합니다
        guest_user = GuestUser.objects.create()
        guest_uuid = str(guest_user.uuid)

    # 사용자 정보를 반환
    response = JsonResponse({'message': 'Guest user retrieved', 'uuid': guest_uuid})
    # 클라이언트 쿠키에 UUID를 저장합니다
    response.set_cookie('guest_uuid', guest_uuid, max_age=365*24*60*60)  # 1년 동안 유지
    return response

def update_guest_preferences(request):
    # UUID로 사용자를 조회
    guest_uuid = request.COOKIES.get('guest_uuid')
    guest_user = get_object_or_404(GuestUser, uuid=guest_uuid)

    # 클라이언트에서 데이터를 전달받아 업데이트
    preferences = request.POST.get('preferences')  # JSON 데이터 예시
    if preferences:
        guest_user.preferences = preferences
        guest_user.save()

    return JsonResponse({'message': 'Preferences updated successfully'})
