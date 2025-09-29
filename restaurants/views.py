from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import connections
import json
import random
import logging

logger = logging.getLogger(__name__)


def _serialize_affiliate_restaurant(row):
    """Convert a raw row from restaurants_affiliate into a JSON-serializable dict."""
    (
        name,
        road_address,
        category_1,
        category_2,
        x,
        y,
        s3_image_urls,
    ) = row

    return {
        'name': name,
        'road_address': road_address,
        'category_1': category_1,
        'category_2': category_2,
        'x': x,
        'y': y,
        's3_image_urls': list(s3_image_urls) if s3_image_urls else [],
    }

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


@csrf_exempt
def get_nearby_restaurants(request):
    """Return up to 15 restaurants within 1km of given coordinates filtered by food names."""
    try:
        data = json.loads(request.body)
        food_names = data.get('food_names', [])
        user_lat = data.get('latitude')
        user_lon = data.get('longitude')

        if user_lat is None or user_lon is None:
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Latitude and longitude are required'}, status=400)

        if not food_names or not all(isinstance(f, str) for f in food_names):
            return JsonResponse({'error_code': 'INVALID_REQUEST', 'message': 'Food names must be a list of strings'}, status=400)

        processed_food_names = [food.replace(" ", "") for food in food_names]

        candidates = []
        with connections['cloudsql'].cursor() as cursor:
            for food in processed_food_names:
                cursor.execute(
                    """
                    SELECT name, road_address, category_1, category_2, x, y
                    FROM daegu_restaurants
                    WHERE category_2 = %s
                      AND y BETWEEN %s - 0.009 AND %s + 0.009
                      AND x BETWEEN %s - 0.009 AND %s + 0.009
                    """,
                    [food, user_lat, user_lat, user_lon, user_lon]
                )
                rows = cursor.fetchall()
                candidates.extend(rows)

        # remove duplicate restaurants by name
        unique_by_name = {}
        for r in candidates:
            if r[0] not in unique_by_name:
                unique_by_name[r[0]] = r

        import math, random

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            d_lat = math.radians(lat2 - lat1)
            d_lon = math.radians(lon2 - lon1)
            a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        filtered = [r for r in unique_by_name.values() if haversine(user_lat, user_lon, r[5], r[4]) < 1]

        random.shuffle(filtered)
        selected = filtered[:15]

        return JsonResponse({
            'restaurants': [
                {
                    'name': r[0],
                    'road_address': r[1],
                    'category_1': r[2],
                    'category_2': r[3],
                    'x': r[4],
                    'y': r[5],
                }
                for r in selected
            ]
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error_code': 'INVALID_JSON', 'message': 'Request body must be valid JSON'}, status=400)
    except Exception as e:
        logger.exception("Unexpected error")
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def get_affiliate_restaurants(request):
    """Return all affiliate restaurants with key details."""
    try:
        with connections['cloudsql'].cursor() as cursor:
            cursor.execute(
                """
                SELECT name, road_address, category_1, category_2, x, y, s3_image_urls
                FROM restaurants_affiliate
                ORDER BY name
                """
            )
            rows = cursor.fetchall()

        restaurants = [_serialize_affiliate_restaurant(row) for row in rows]

        return JsonResponse({'restaurants': restaurants}, status=200)
    except Exception as exc:
        logger.exception("Failed to fetch affiliate restaurants")
        return JsonResponse(
            {'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(exc)}'},
            status=500,
        )


@require_http_methods(["GET"])
def get_affiliate_restaurant_detail(request):
    """Return full affiliate restaurant row matched by name (exact match preferred)."""
    name_query = request.GET.get('name')

    if not name_query:
        return JsonResponse(
            {'error_code': 'INVALID_REQUEST', 'message': 'Query parameter "name" is required'},
            status=400,
        )

    try:
        with connections['cloudsql'].cursor() as cursor:
            # Try exact match first for stability.
            cursor.execute(
                "SELECT * FROM restaurants_affiliate WHERE name = %s",
                [name_query],
            )
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description]

            if not rows:
                cursor.execute(
                    "SELECT * FROM restaurants_affiliate WHERE name ILIKE %s",
                    [f'%{name_query}%'],
                )
                rows = cursor.fetchall()
                columns = [col[0] for col in cursor.description]

        if not rows:
            return JsonResponse(
                {'error_code': 'NOT_FOUND', 'message': 'Affiliate restaurant not found'},
                status=404,
            )

        if len(rows) > 1:
            matched_names = [dict(zip(columns, row)).get('name') for row in rows]
            return JsonResponse(
                {
                    'error_code': 'MULTIPLE_MATCHES',
                    'message': 'Multiple restaurants matched; please provide a more specific name',
                    'matches': matched_names,
                },
                status=409,
            )

        restaurant = dict(zip(columns, rows[0]))

        if 's3_image_urls' in restaurant and restaurant['s3_image_urls'] is None:
            restaurant['s3_image_urls'] = []

        return JsonResponse({'restaurant': restaurant}, status=200)
    except Exception as exc:
        logger.exception("Failed to fetch affiliate restaurant detail")
        return JsonResponse(
            {'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(exc)}'},
            status=500,
        )
