# 게스트 사용자 뷰
from django.http import JsonResponse
from .models import GuestUser
from restaurants.models import Restaurant
from django.core.exceptions import ValidationError
import json
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def retrieve_guest_user(request):
    uuid = request.GET.get('uuid') # 요청에서 UUID 가져오기
    if not uuid:
        # 새 게스트 사용자 생성
        guest_user = GuestUser.objects.create()
        return JsonResponse({'uuid': str(guest_user.uuid)}) # 생성된 게스트 사용자의 UUID를 반환
    try:
        # UUID로 게스트 사용자 검색
        guest_user = GuestUser.objects.get(uuid=uuid) # ORM으로 가져온 uuid에 맞는 객체 찾기
        return JsonResponse({
            'uuid': str(guest_user.uuid),
            'type_code': guest_user.type_code,
            'favorite_restaurants': guest_user.get_favorite_restaurants(),
        })
    except GuestUser.DoesNotExist:
        # db에 게스트 사용자가 없는 경우
        return JsonResponse({'status': 'error', 'message': 'Guest user not found'}, status=404)

# @csrf_exempt
# def update_guest_user_type_code(request):
#     # 유형 코드 업데이트
#     data = request.GET  # GET 요청으로 데이터 받음
#     uuid = request.GET.get('uuid') # 요청에서 UUID 가져오기
#     type_code = data.get('type_code') # 유형 코드 받아오기
#     try:
#         guest_user = GuestUser.objects.get(uuid=uuid) # 게스트 사용자 검색
#         guest_user.type_code = type_code # 유형 코드 업데이트
#         guest_user.save() # 저장
#         return JsonResponse({'status': 'success', 'message': '게스트 사용자 유형 코드 업데이트 성공'})
#     except GuestUser.DoesNotExist:
#         return JsonResponse({'status': 'error', 'message': '게스트 사용자 없음'}, status=404)

@csrf_exempt
def update_guest_user_type_code(request):
    """Update guest user's type_code.

    Accepts:
    - GET: query params `uuid`, `type_code`
    - POST: JSON body { uuid, type_code } or form-encoded fields
    """

    uuid = None
    type_code = None

    try:
        if request.method == 'GET':
            data = request.GET
            uuid = data.get('uuid')
            type_code = data.get('type_code')
        elif request.method == 'POST':
            # Try JSON first
            try:
                body = request.body.decode('utf-8') or ''
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {}

            uuid = payload.get('uuid') or request.POST.get('uuid')
            type_code = payload.get('type_code') or request.POST.get('type_code')
        else:
            return JsonResponse({'status': 'error', 'message': '허용되지 않은 메서드입니다.'}, status=405)

        # 요청 데이터 검증
        if not uuid:
            return JsonResponse({'status': 'error', 'message': 'UUID가 제공되지 않았습니다.'}, status=400)
        if not type_code:
            return JsonResponse({'status': 'error', 'message': '유형 코드가 제공되지 않았습니다.'}, status=400)

        # 게스트 사용자 검색 및 업데이트
        try:
            guest_user = GuestUser.objects.get(uuid=uuid)
        except GuestUser.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '게스트 사용자 없음'}, status=404)

        try:
            guest_user.type_code = type_code
            guest_user.save(update_fields=['type_code'])
            return JsonResponse({'status': 'success', 'message': '게스트 사용자 유형 코드 업데이트 성공'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': f'유형 코드 업데이트 실패: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'유형 코드 업데이트 중 오류 발생: {str(e)}'}, status=500)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'알 수 없는 오류 발생: {str(e)}'}, status=500)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def update_guest_user_favorite_restaurants(request):
    # 찜 음식점 업데이트
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'}, status=405)
    
    try:
        data = json.loads(request.body)  # 요청 본문에서 JSON 데이터 파싱
        uuid = data.get('uuid')  # 게스트 사용자의 UUID
        restaurant_name = data.get('restaurant')  # 음식점 이름
        action = data.get('action')  # 동작 ('add' 또는 'remove')

        if not uuid or not restaurant_name or action not in ['add', 'remove']:
            return JsonResponse({'status': 'error', 'message': '필수 파라미터가 누락되었습니다.'}, status=400)

        guest_user = GuestUser.objects.get(uuid=uuid)
        restaurant_obj = Restaurant.objects.filter(name=restaurant_name).first()
        if not restaurant_obj:
            return JsonResponse({'status': 'error', 'message': '음식점을 찾을 수 없습니다.'}, status=404)

        favorite_restaurants = json.loads(guest_user.favorite_restaurants or '[]')

        if action == 'add':
            # 음식점 추가
            if restaurant_name not in favorite_restaurants:
                favorite_restaurants.append(restaurant_name)
                restaurant_obj.liked_count = (restaurant_obj.liked_count or 0) + 1
                restaurant_obj.save(update_fields=['liked_count'])
                print(
                    f"Liked count for {restaurant_obj.name} increased to {restaurant_obj.liked_count}"
                )
        elif action == 'remove':
            # 음식점 제거
            if restaurant_name in favorite_restaurants:
                favorite_restaurants.remove(restaurant_name)
                if restaurant_obj.liked_count and restaurant_obj.liked_count > 0:
                    restaurant_obj.liked_count -= 1
                    restaurant_obj.save(update_fields=['liked_count'])
                    print(
                        f"Liked count for {restaurant_obj.name} decreased to {restaurant_obj.liked_count}"
                    )

        # 업데이트된 리스트를 JSON 형식으로 저장
        guest_user.favorite_restaurants = json.dumps(favorite_restaurants)
        guest_user.save()

        return JsonResponse({'status': 'success', 'message': '게스트 사용자 찜 음식점 업데이트 성공', 'favorites': favorite_restaurants})
    
    except GuestUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '게스트 사용자를 찾을 수 없습니다.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '잘못된 JSON 데이터입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_guest_user_fcm_token(request):
    """Update the FCM token for a guest user."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'}, status=405)

    try:
        data = json.loads(request.body)
        uuid = data.get('uuid')
        fcm_token = data.get('fcm_token')

        if not uuid or not fcm_token:
            return JsonResponse({'status': 'error', 'message': '필수 파라미터가 누락되었습니다.'}, status=400)

        guest_user = GuestUser.objects.get(uuid=uuid)
        guest_user.fcm_token = fcm_token
        guest_user.save(update_fields=['fcm_token'])

        return JsonResponse({'status': 'success', 'message': 'FCM 토큰 업데이트 성공'})

    except GuestUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '게스트 사용자를 찾을 수 없습니다.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '잘못된 JSON 데이터입니다.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
