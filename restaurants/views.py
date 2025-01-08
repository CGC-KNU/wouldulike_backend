from django.http import JsonResponse
from .models import Restaurant
from food_by_type.models import FoodTasteType
from guests.models import GuestUser
import random
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def get_restaurants_by_foods(request, user_uuid):
    # 사용자 uuid로 유형 코드 가져오기
    try:
        guest = GuestUser.objects.get(uuid=user_uuid)
        type_code = guest.type_code
    except GuestUser.DoesNotExist:
        return JsonResponse({'error_code': 'USER_NOT_FOUND', 'message': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

    # 유형 코드로 음식 목록 가져오기
    try:
        food_type = FoodTasteType.objects.get(type_code=type_code)
        foods = food_type.foods
        random_foods = random.sample(foods, min(len(foods), 6))
    except FoodTasteType.DoesNotExist:
        return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Type code not found'}, status=404)
    except ValueError as e:
        return JsonResponse({'error_code': 'FOODS_SAMPLE_ERROR', 'message': f'Error sampling foods: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

    # 음식 명칭 기반으로 음식점 검색
    try:
        matching_restaurants = Restaurant.objects.filter(food_name__in=random_foods).values('food_name', 'restaurant_name')

        # 음식점이 없는 경우
        if not matching_restaurants.exists():
            return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the selected foods'}, status=404)

        # 음식점을 랜덤으로 6개만 추출
        random_restaurants = matching_restaurants.order_by('?')[:6]

        # 결과 반환
        result = list(random_restaurants)
        return JsonResponse({'restaurants': result})
    except Exception as e:
        return JsonResponse({'error_code': 'DATABASE_QUERY_ERROR', 'message': f'Error querying restaurants: {str(e)}'}, status=500)