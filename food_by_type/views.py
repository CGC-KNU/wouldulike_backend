import random
from django.http import JsonResponse
from .models import TypeCode, TypeCodeFood, Food
from guests.models import GuestUser
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from redis import Redis
from django.conf import settings
from django.core.cache import cache


@csrf_exempt
def get_random_foods(request):
    """
    Deprecated endpoint.
    더 이상 사용하지 않으며, 항상 404를 반환합니다.
    프론트는 이 엔드포인트 실패 시 fallback 로직을 사용하도록 구현되어 있습니다.
    """
    return JsonResponse(
        {
            "error_code": "DEPRECATED_ENDPOINT",
            "message": "This endpoint is no longer supported.",
        },
        status=404,
    )
    

# Redis 클라이언트 설정 (Django settings에 Redis 설정 필요)
# redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0, decode_responses=True)
redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    password=settings.REDIS_PASSWORD,  # 비밀번호 추가
    decode_responses=True,
)

def get_unique_random_foods(request):
    try:
        data = request.GET
        user_uuid = data.get('uuid')
        print(f"Received UUID: {user_uuid}")

        if not user_uuid:
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'UUID is required'}, status=400)
        
        try:
            guest_user = GuestUser.objects.get(uuid=user_uuid)
            type_code = guest_user.type_code
            print(f"GuestUser found: {guest_user}, TypeCode: {type_code}")
        except ObjectDoesNotExist:
            return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Invalid UUID or no type code found'}, status=404)
        
        try:
            type_code_obj = TypeCode.objects.get(type_code=type_code)
            type_code_id = type_code_obj.type_code_id
            print(f"TypeCode found: {type_code_obj}, TypeCodeID: {type_code_id}")
        except TypeCode.DoesNotExist:
            return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Type code not found in database'}, status=404)

        # Step 1: 전체 food_id 조회 (음식 정보는 나중에)
        food_ids = list(TypeCodeFood.objects.filter(type_code_id=type_code_id).values_list('food_id', flat=True))
        print(f"Food IDs retrieved: {food_ids}")

        if not food_ids:
            return JsonResponse({'error_code': 'NO_FOOD_FOUND', 'message': 'No food available for this type code'}, status=404)

        # Step 2: 캐시에서 이전에 추천된 food_id 확인
        cache_key = f'user:{user_uuid}:foods'
        try:
            cached_food_ids = redis_client.lrange(cache_key, 0, -1)
            cached_food_ids_set = set(cached_food_ids)
            print(f"Cached food_ids: {cached_food_ids}")
        except Exception as e:
            # 캐시 문제 시 중복제거 기능을 비활성화하고 계속 진행
            print(f"Cache read error (fallback to no-cache): {e}")
            cached_food_ids_set = set()

        # Step 3: 중복 제거된 food_id만 필터링
        available_food_ids = [fid for fid in food_ids if str(fid) not in cached_food_ids_set]
        print(f"Available food_ids after filtering: {available_food_ids}")

        if not available_food_ids:
            return JsonResponse({'error_code': 'NOT_ENOUGH_FOOD', 'message': 'No unique food options available'}, status=404)

        # Step 4: 랜덤으로 최대 10개의 food_id 선택
        try:
            selected_food_ids = random.sample(available_food_ids, min(len(available_food_ids), 10))
            print(f"Randomly selected food_ids: {selected_food_ids}")
        except Exception as e:
            print(f"Random selection error: {e}")
            return JsonResponse({'error_code': 'RANDOM_SELECTION_ERROR', 'message': f'Error selecting random foods: {str(e)}'}, status=500)

        # Step 5: 최종 선택된 food_id들에 대한 음식 정보 조회
        try:
            random_foods = list(Food.objects.filter(food_id__in=selected_food_ids).values('food_id', 'food_name', 'description', 'food_image_url'))
            print(f"Food info retrieved for selected foods: {random_foods}")
        except Exception as e:
            print(f"Food info query error: {e}")
            return JsonResponse({'error_code': 'FOOD_INFO_QUERY_ERROR', 'message': f'Error retrieving food info: {str(e)}'}, status=500)

        # Step 6: 캐시 업데이트
        try:
            redis_client.rpush(cache_key, *map(str, selected_food_ids))
            redis_client.ltrim(cache_key, -80, -1)
            redis_client.expire(cache_key, 600)
            print(f"Updated cache: {redis_client.lrange(cache_key, 0, -1)}")
        except Exception as e:
            # 캐시 업데이트 실패 시에도 추천은 반환
            print(f"Cache update error (ignored): {e}")

        return JsonResponse({'random_foods': random_foods})

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
