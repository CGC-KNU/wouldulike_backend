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
                    SELECT name, road_address, category_1, category_2, x, y
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
                    'category_2': r[3],
                    'x': r[4],
                    'y': r[5]
                } for r in unique_by_name.values()
            ]
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
    except Exception as e:
        logger.exception("Unexpected error")
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
