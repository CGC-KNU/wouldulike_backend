# 게스트 사용자 뷰
from django.http import JsonResponse
from .models import GuestUser
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
    # 유형 코드 업데이트
    data = request.GET  # GET 요청으로 데이터 받음
    uuid = data.get('uuid')  # 요청에서 UUID 가져오기
    type_code = data.get('type_code')  # 유형 코드 받아오기

    # 요청 데이터 검증
    if not uuid:
        return JsonResponse({'status': 'error', 'message': 'UUID가 제공되지 않았습니다.'}, status=400)
    if not type_code:
        return JsonResponse({'status': 'error', 'message': '유형 코드가 제공되지 않았습니다.'}, status=400)

    try:
        # 게스트 사용자 검색
        guest_user = GuestUser.objects.get(uuid=uuid)
        try:
            # 유형 코드 업데이트
            guest_user.type_code = type_code
            guest_user.save()
            return JsonResponse({'status': 'success', 'message': '게스트 사용자 유형 코드 업데이트 성공'})
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': f'유형 코드 업데이트 실패: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'유형 코드 업데이트 중 오류 발생: {str(e)}'}, status=500)
    except GuestUser.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '게스트 사용자 없음'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'알 수 없는 오류 발생: {str(e)}'}, status=500)

def update_guest_user_favorite_restaurants(request):
    # 찜 음식점 업데이트
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST 요청만 허용됩니다.'}, status=405)
    
    try:
        data = json.loads(request.body)  # 요청 본문에서 JSON 데이터 파싱
        uuid = data.get('uuid')  # 게스트 사용자의 UUID
        restaurant = data.get('restaurant')  # 음식점 이름
        action = data.get('action')  # 동작 ('add' 또는 'remove')

        if not uuid or not restaurant or action not in ['add', 'remove']:
            return JsonResponse({'status': 'error', 'message': '필수 파라미터가 누락되었습니다.'}, status=400)

        guest_user = GuestUser.objects.get(uuid=uuid)

        favorite_restaurants = json.loads(guest_user.favorite_restaurants or '[]')

        if action == 'add':
            # 음식점 추가
            if restaurant not in favorite_restaurants:
                favorite_restaurants.append(restaurant)
        elif action == 'remove':
            # 음식점 제거
            if restaurant in favorite_restaurants:
                favorite_restaurants.remove(restaurant)

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