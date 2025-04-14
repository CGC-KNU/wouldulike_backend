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
    # GET 요청에서 UUID 가져오기
    try:
        data = request.GET
        user_uuid = data.get('uuid')
        if not user_uuid:
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'UUID is required'}, status=400)

        # UUID로 GuestUser 조회 및 type_code 가져오기
        try:
            guest_user = GuestUser.objects.get(uuid=user_uuid)
            type_code = guest_user.type_code
        except ObjectDoesNotExist:
            return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Invalid UUID or no type code found'}, status=404)

    except Exception as e:
        return JsonResponse({'error_code': 'TYPE_CODE_RETRIEVAL_ERROR', 'message': f'Error retrieving type code: {str(e)}'}, status=500)

    # 유형 코드로 type_code_id를 가져오기
    try:
    # TypeCode 객체 검색
        type_code_obj = TypeCode.objects.get(type_code=type_code)
    # 검색된 객체에서 type_code_id 가져오기
        type_code_id = type_code_obj.type_code_id
    except TypeCode.DoesNotExist:
        return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Type code not found in database'}, status=404)
    except Exception as e:
        return JsonResponse({'error_code': 'TYPE_CODE_QUERY_ERROR', 'message': f'Error querying type code: {str(e)}'}, status=500)

    # type_code_id로 food_id들을 가져오기 (type_code_foods 테이블에서)
    try:
        food_ids = TypeCodeFood.objects.filter(type_code_id=type_code_id).values_list('food_id', flat=True)
    except Exception as e:
        return JsonResponse({'error_code': 'FOOD_ID_RETRIEVAL_ERROR', 'message': f'Error retrieving food IDs: {str(e)}'}, status=500)

    # food_ids로 foods 테이블에서 food_name과 description을 가져오기
    try:
        foods = Food.objects.filter(food_id__in=food_ids).values('food_id', 'food_name', 'description', 'food_image_url')
    except Exception as e:
        return JsonResponse({'error_code': 'FOODS_RETRIEVAL_ERROR', 'message': f'Error retrieving food details: {str(e)}'}, status=500)

    # 랜덤으로 3개 음식 선택
    try:
        random_foods = random.sample(list(foods), min(len(foods), 5))  # 최대 5개 음식
        return JsonResponse({'random_foods': random_foods})
    except ValueError as e:
        return JsonResponse({'error_code': 'FOOD_SAMPLING_ERROR', 'message': f'Error sampling foods: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
    

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

        food_ids = list(TypeCodeFood.objects.filter(type_code_id=type_code_id).values_list('food_id', flat=True))
        foods = list(Food.objects.filter(food_id__in=food_ids).values('food_id', 'food_name', 'description', 'food_image_url'))
        print(f"Foods retrieved: {foods}")

        if not foods:
            return JsonResponse({'error_code': 'NO_FOOD_FOUND', 'message': 'No food available for this type code'}, status=404)

        # Redis 캐시 확인
        cache_key = f'user:{user_uuid}:foods'
        try:
            cached_foods = redis_client.lrange(cache_key, 0, -1)
            print(f"Step 1: Cached foods retrieved for key {cache_key}: {cached_foods}")
        except Exception as e:
            print(f"Step 1 Error: Failed to retrieve cached foods for key {cache_key}: {e}")
            return JsonResponse({'error_code': 'CACHE_READ_ERROR', 'message': f'Error reading cache: {str(e)}'}, status=500)

        # 중복되지 않는 음식 필터링
        try:
            available_foods = [food for food in foods if food['food_name'] not in cached_foods]
            print(f"Step 2: Available foods after filtering cached foods: {available_foods}")
            if not available_foods:
                return JsonResponse({'error_code': 'NOT_ENOUGH_FOOD', 'message': 'No unique food options available'}, status=404)
        except Exception as e:
            print(f"Step 2 Error: Error filtering available foods: {e}")
            return JsonResponse({'error_code': 'FOOD_FILTER_ERROR', 'message': f'Error filtering foods: {str(e)}'}, status=500)

        # 랜덤으로 10개 선택
        try:
            random_foods = random.sample(available_foods, min(len(available_foods), 10))
            print(f"Step 3: Random foods selected: {random_foods}")
        except Exception as e:
            print(f"Step 3 Error: Error selecting random foods: {e}")
            return JsonResponse({'error_code': 'RANDOM_SELECTION_ERROR', 'message': f'Error selecting random foods: {str(e)}'}, status=500)

        # Redis 캐시 갱신
        try:
            new_food_names = [food['food_name'] for food in random_foods]
            if new_food_names:
                redis_client.rpush(cache_key, *new_food_names)
                redis_client.ltrim(cache_key, -80, -1)
                redis_client.expire(cache_key, 600)
                print(f"Step 4: Updated cache for key {cache_key}: {redis_client.lrange(cache_key, 0, -1)}")
        except Exception as e:
            print(f"Step 4 Error: Failed to update cache for key {cache_key}: {e}")
            return JsonResponse({'error_code': 'CACHE_UPDATE_ERROR', 'message': f'Error updating cache: {str(e)}'}, status=500)

        return JsonResponse({'random_foods': random_foods})
    
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
