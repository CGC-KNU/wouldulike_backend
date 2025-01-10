import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Restaurant

@csrf_exempt
def get_random_restaurants(request):
    try:
        # 요청 데이터 파싱
        data = json.loads(request.body)
        food_names = data.get('food_names', [])
        if not food_names:
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names are required'}, status=400)

        # 음식명으로 음식점 검색
        restaurants = Restaurant.objects.filter(category_2__in=food_names).values('name', 'road_address', 'category_2')
        
        # 음식점 데이터가 없을 경우 처리
        if not restaurants:
            return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

        # 랜덤으로 5개 음식점 선택
        random_restaurants = random.sample(list(restaurants), min(len(restaurants), 5))

        # JSON 응답 반환
        return JsonResponse({'random_restaurants': list(random_restaurants)}, status=200)

    except ValueError as e:
        return JsonResponse({'error_code': 'RANDOM_SAMPLING_ERROR', 'message': f'Error sampling restaurants: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
