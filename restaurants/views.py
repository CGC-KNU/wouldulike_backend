# import random
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# import json
# from .models import Restaurant

# @csrf_exempt
# def get_random_restaurants(request):
#     try:
#         # 요청 데이터 파싱
#         data = json.loads(request.body)
#         food_names = data.get('food_names', [])
#         if not food_names:
#             return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names are required'}, status=400)

#         # 음식명으로 음식점 검색
#         restaurants = Restaurant.objects.filter(category_2__in=food_names).values('name', 'road_address', 'category_2')
        
#         # 음식점 데이터가 없을 경우 처리
#         if not restaurants:
#             return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

#         # 랜덤으로 5개 음식점 선택
#         random_restaurants = random.sample(list(restaurants), min(len(restaurants), 5))

#         # JSON 응답 반환
#         return JsonResponse({'random_restaurants': list(random_restaurants)}, status=200)

#     except json.JSONDecodeError:
#         return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
#     except ValueError as e:
#         return JsonResponse({'error_code': 'RANDOM_SAMPLING_ERROR', 'message': f'Error sampling restaurants: {str(e)}'}, status=400)
#     except Exception as e:
#         return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

import random
import psycopg2
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decouple import config

@csrf_exempt
def get_random_restaurants(request):
    try:
        # 요청 데이터 파싱
        data = json.loads(request.body)
        food_names = data.get('food_names', [])
        if not food_names:
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names are required'}, status=400)

        # Redshift 연결 설정
        conn = psycopg2.connect(
            dbname=config('REDSHIFT_DB_NAME'),
            user=config('REDSHIFT_USER'),
            password=config('REDSHIFT_PASSWORD'),
            host=config('REDSHIFT_HOST'),
            port=config('REDSHIFT_PORT')
        )
        cur = conn.cursor()

        # 음식명으로 음식점 검색
        placeholders = ', '.join(['%s'] * len(food_names))  # SQL IN 절에 사용할 자리표시자
        query = f"""
            SELECT name, road_address, category_2
            FROM restaurant_new
            WHERE category_2 IN ({placeholders})
        """
        cur.execute(query, food_names)
        restaurants = cur.fetchall()

        # Redshift 연결 종료
        cur.close()
        conn.close()

        # 음식점 데이터가 없을 경우 처리
        if not restaurants:
            return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

        # 랜덤으로 15개 음식점 선택
        random_restaurants = random.sample(restaurants, min(len(restaurants), 15))

        # JSON 응답 반환
        return JsonResponse({'random_restaurants': [
            {'name': r[0], 'road_address': r[1], 'category_2': r[2]} for r in random_restaurants
        ]}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
    except psycopg2.Error as e:
        return JsonResponse({'error_code': 'DATABASE_ERROR', 'message': f'Database error: {str(e)}'}, status=500)
    except ValueError as e:
        return JsonResponse({'error_code': 'RANDOM_SAMPLING_ERROR', 'message': f'Error sampling restaurants: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
