# import psycopg2
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# import json
# from decouple import config

# @csrf_exempt
# def get_random_restaurants(request):
#     try:
#         # 요청 데이터 파싱
#         data = json.loads(request.body)
#         food_names = data.get('food_names', [])

#         if not food_names or not all(isinstance(f, str) for f in food_names):
#             return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

#         # **띄어쓰기 제거 후 새로운 리스트 생성**
#         processed_food_names = [food.replace(" ", "") for food in food_names]

#         # Redshift 연결 설정
#         conn = psycopg2.connect(
#             dbname=config('REDSHIFT_DB_NAME'),
#             user=config('REDSHIFT_USER'),
#             password=config('REDSHIFT_PASSWORD'),
#             host=config('REDSHIFT_HOST'),
#             port=config('REDSHIFT_PORT')
#         )
#         cur = conn.cursor()

#         # SQL에서 직접 랜덤 샘플링 수행
#         placeholders = ', '.join(['%s'] * len(processed_food_names))
#         query = f"""
#             SELECT name, road_address, category_1, category_2
#             FROM restaurant_new
#             WHERE category_2 IN ({placeholders})
#             ORDER BY RANDOM()
#             LIMIT 15
#         """
#         cur.execute(query, processed_food_names)  # 가공된 food_names 리스트 전달
#         restaurants = cur.fetchall()

#         # Redshift 연결 종료
#         cur.close()
#         conn.close()

#         # 음식점 데이터가 없을 경우 처리
#         if not restaurants:
#             return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

#         # JSON 응답 반환
#         return JsonResponse({'random_restaurants': [
#             {'name': r[0], 'road_address': r[1], 'category_1': r[2], 'category_2': r[3]} for r in restaurants
#         ]}, status=200)

#     except json.JSONDecodeError:
#         return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
#     except psycopg2.Error as e:
#         return JsonResponse({'error_code': 'DATABASE_ERROR', 'message': f'Database error: {str(e)}'}, status=500)
#     except Exception as e:
#         return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.db.models.functions import Random  # 🔸 랜덤 정렬을 위한 ORM 함수
# from restaurants.models import Restaurant
# import json

# @csrf_exempt
# def get_random_restaurants(request):
#     try:
#         # 요청 데이터 파싱
#         data = json.loads(request.body)
#         food_names = data.get('food_names', [])

#         if not food_names or not all(isinstance(f, str) for f in food_names):
#             return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

#         # 띄어쓰기 제거
#         processed_food_names = [food.replace(" ", "") for food in food_names]

#         # Cloud SQL(DB)에서 랜덤 추출 15개 (cloudsql DB alias 사용)
#         sampled = Restaurant.objects.using('cloudsql') \
#             .filter(category_2__in=processed_food_names) \
#             .order_by(Random())[:15]

#         if not sampled:
#             return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

#         # return JsonResponse({
#         #     'random_restaurants': [
#         #         {
#         #             'name': r.name,
#         #             'road_address': r.road_address,
#         #             'category_1': r.category_1,
#         #             'category_2': r.category_2
#         #         } for r in sampled
#         #     ]
#         # }, status=200)

#         return JsonResponse({
#             'random_restaurants': list(
#                 sampled.values('name', 'road_address', 'category_1', 'category_2')
#             )
#         }, status=200)

#     except json.JSONDecodeError:
#         return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
#     except Exception as e:
#         return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connections  # 데이터베이스 alias 사용
import json
import random

@csrf_exempt
def get_random_restaurants(request):
    try:
        data = json.loads(request.body)
        food_names = data.get('food_names', [])

        if not food_names or not all(isinstance(f, str) for f in food_names):
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

        # 🔸 프론트에서 받은 음식명의 공백 제거 (DB에는 공백이 없다고 가정)
        processed_food_names = [food.replace(" ", "") for food in food_names]

        with connections['cloudsql'].cursor() as cursor:
            # Step 1: 총 개수 조회
            placeholders = ', '.join(['%s'] * len(processed_food_names))
            count_query = f"""
                SELECT COUNT(*)
                FROM daegu_restaurants
                WHERE category_2 IN ({placeholders})
            """
            cursor.execute(count_query, processed_food_names)
            total_count = cursor.fetchone()[0]

            if total_count == 0:
                return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

            # Step 2: 랜덤 offset 계산
            offset = max(0, random.randint(0, max(0, total_count - 15)))

            # Step 3: 랜덤 추출
            query = f"""
                SELECT name, road_address, category_1, category_2
                FROM daegu_restaurants
                WHERE category_2 IN ({placeholders})
                OFFSET %s LIMIT 15
            """
            cursor.execute(query, processed_food_names + [offset])
            rows = cursor.fetchall()

        return JsonResponse({
            'random_restaurants': [
                {
                    'name': r[0],
                    'road_address': r[1],
                    'category_1': r[2],
                    'category_2': r[3]
                } for r in rows
            ]
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
