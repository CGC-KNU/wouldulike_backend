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

# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.db import connections  # 데이터베이스 alias 사용
# import json
# import random

# @csrf_exempt
# def get_random_restaurants(request):
#     try:
#         data = json.loads(request.body)
#         food_names = data.get('food_names', [])

#         if not food_names or not all(isinstance(f, str) for f in food_names):
#             return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

#         # 🔸 프론트에서 받은 음식명의 공백 제거 (DB에는 공백이 없다고 가정)
#         processed_food_names = [food.replace(" ", "") for food in food_names]

#         with connections['cloudsql'].cursor() as cursor:
#             # Step 1: 총 개수 조회
#             placeholders = ', '.join(['%s'] * len(processed_food_names))
#             count_query = f"""
#                 SELECT COUNT(*)
#                 FROM daegu_restaurants
#                 WHERE category_2 IN ({placeholders})
#             """
#             cursor.execute(count_query, processed_food_names)
#             total_count = cursor.fetchone()[0]

#             if total_count == 0:
#                 return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

#             # Step 2: 랜덤 offset 계산
#             offset = max(0, random.randint(0, max(0, total_count - 15)))

#             # Step 3: 랜덤 추출
#             query = f"""
#                 SELECT name, road_address, category_1, category_2
#                 FROM daegu_restaurants
#                 WHERE category_2 IN ({placeholders})
#                 OFFSET %s LIMIT 15
#             """
#             cursor.execute(query, processed_food_names + [offset])
#             rows = cursor.fetchall()

#         return JsonResponse({
#             'random_restaurants': [
#                 {
#                     'name': r[0],
#                     'road_address': r[1],
#                     'category_1': r[2],
#                     'category_2': r[3]
#                 } for r in rows
#             ]
#         }, status=200)

#     except json.JSONDecodeError:
#         return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
#     except Exception as e:
#         return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.db import connections
# import json
# import random
# import logging

# logger = logging.getLogger(__name__)  # 로그 기록용

# @csrf_exempt
# def get_random_restaurants(request):
#     try:
#         data = json.loads(request.body)
#         food_names = data.get('food_names', [])

#         logger.info(f"Received food_names: {food_names}")

#         if not food_names or not all(isinstance(f, str) for f in food_names):
#             return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

#         # 1️⃣ 음식명 전처리
#         processed_food_names = [food.replace(" ", "") for food in food_names]
#         logger.info(f"Processed food_names: {processed_food_names}")

#         all_candidates = []

#         logger.info("🔗 Attempting to connect to Cloud SQL")
#         with connections['cloudsql'].cursor() as cursor:
#             logger.info("✅ Connected to Cloud SQL")

#             for food in processed_food_names:
#                 logger.info(f"🍽 Processing category: {food}")

#                 # Step 1: 해당 카테고리 음식점 수 조회
#                 count_query = "SELECT COUNT(*) FROM daegu_restaurants WHERE category_2 = %s"
#                 logger.info(f"🟡 Running count query: {count_query}")
#                 logger.info(f"🟡 With param: {food}")
#                 cursor.execute(count_query, [food])

#                 total = cursor.fetchone()[0]
#                 logger.info(f"🔢 Total count for '{food}': {total}")

#                 if total == 0:
#                     continue

#                 # Step 2: 랜덤 offset 계산
#                 offset = max(0, random.randint(0, max(0, total - 2)))
#                 logger.info(f"🎲 Random offset for '{food}': {offset}")

#                 # Step 3: 부분 샘플 가져오기
#                 select_query = """
#                     SELECT name, road_address, category_1, category_2
#                     FROM daegu_restaurants
#                     WHERE category_2 = %s
#                     OFFSET %s LIMIT 2
#                 """
#                 logger.info(f"🟢 Running select query: {select_query}")
#                 logger.info(f"🟢 With params: [{food}, {offset}]")
#                 cursor.execute(select_query, [food, offset])
#                 rows = cursor.fetchall()

#                 logger.info(f"📦 Retrieved {len(rows)} rows for '{food}'")
#                 all_candidates.extend(rows)

#         logger.info(f"🎯 Total candidates collected: {len(all_candidates)}")

#         if not all_candidates:
#             return JsonResponse({'error_code': 'NO_RESTAURANTS_FOUND', 'message': 'No restaurants found for the given food names'}, status=404)

#         selected = random.sample(all_candidates, min(15, len(all_candidates)))

#         return JsonResponse({
#             'random_restaurants': [
#                 {
#                     'name': r[0],
#                     'road_address': r[1],
#                     'category_1': r[2],
#                     'category_2': r[3]
#                 } for r in selected
#             ]
#         }, status=200)

#     except json.JSONDecodeError:
#         logger.exception("❌ JSON parsing failed")
#         return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
#     except Exception as e:
#         logger.exception("❗️Unexpected error")
#         return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connections
import json
import random
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def get_random_restaurants(request):
    try:
        data = json.loads(request.body)
        food_names = data.get('food_names', [])
        logger.info(f"Received food_names: {food_names}")

        if not food_names or not all(isinstance(f, str) for f in food_names):
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

        processed_food_names = [food.replace(" ", "") for food in food_names]
        logger.info(f"Processed food_names: {processed_food_names}")

        restaurants_by_category = {}
        total_candidates = []

        with connections['cloudsql'].cursor() as cursor:
            for food in processed_food_names:
                logger.info(f"Processing category: {food}")

                cursor.execute("SELECT COUNT(*) FROM daegu_restaurants WHERE category_2 = %s", [food])
                total = cursor.fetchone()[0]
                logger.info(f"Total for {food}: {total}")

                if total == 0:
                    continue

                offset = max(0, random.randint(0, max(0, total - 100)))
                logger.info(f"Offset for {food}: {offset}")

                cursor.execute("""
                    SELECT name, road_address, category_1, category_2
                    FROM daegu_restaurants
                    WHERE category_2 = %s
                    OFFSET %s LIMIT 100
                """, [food, offset])
                rows = cursor.fetchall()

                restaurants_by_category[food] = rows

        logger.info(f"Collected category samples: {[len(v) for v in restaurants_by_category.values()]}")

        # 🔸 카테고리별 균등 분배로 추출
        selected = []
        max_total = 15
        categories = list(restaurants_by_category.keys())
        max_per_cat = max_total // len(categories) if categories else 0

        for cat in categories:
            candidates = restaurants_by_category[cat]
            selected.extend(random.sample(candidates, min(max_per_cat, len(candidates))))

        # 🔸 음식점 이름 중복 제거
        unique_by_name = {}
        for r in selected:
            if r[0] not in unique_by_name:
                unique_by_name[r[0]] = r

        logger.info(f"Initial unique count: {len(unique_by_name)}")

        # 🔸 부족한 수 보충
        if len(unique_by_name) < max_total:
            needed = max_total - len(unique_by_name)
            all_selected_names = set(unique_by_name.keys())

            all_remaining = [
                r for rest_list in restaurants_by_category.values()
                for r in rest_list if r[0] not in all_selected_names
            ]

            random.shuffle(all_remaining)
            for r in all_remaining:
                if len(unique_by_name) >= max_total:
                    break
                if r[0] not in unique_by_name:
                    unique_by_name[r[0]] = r

        logger.info(f"Final unique selections: {len(unique_by_name)}")

        return JsonResponse({
            'random_restaurants': [
                {
                    'name': r[0],
                    'road_address': r[1],
                    'category_1': r[2],
                    'category_2': r[3]
                } for r in unique_by_name.values()
            ]
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
    except Exception as e:
        logger.exception("Unexpected error")
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
