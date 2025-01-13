import random
from django.http import JsonResponse
from .models import TypeCode, TypeCodeFood, Food
from guests.models import GuestUser
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt

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
        random_foods = random.sample(list(foods), min(len(foods), 3))  # 최대 3개 음식
        return JsonResponse({'random_foods': random_foods})
    except ValueError as e:
        return JsonResponse({'error_code': 'FOOD_SAMPLING_ERROR', 'message': f'Error sampling foods: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)