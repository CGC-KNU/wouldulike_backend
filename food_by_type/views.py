import random
from django.http import JsonResponse
from .models import TypeCode, TypeCodeFood, Food
from guests.models import GuestUser
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt

def get_type_code_from_uuid(user_uuid):
    try:
        guest_user = GuestUser.objects.get(uuid=user_uuid)
        return guest_user.type_code
    except ObjectDoesNotExist:
        return None

@csrf_exempt
def get_random_foods(request, user_uuid):
    # guests 앱에서 uuid를 사용해 유형 코드를 가져오는 로직임
    try:
        type_code = get_type_code_from_uuid(user_uuid)
    except Exception as e:
        return JsonResponse({'error_code': 'TYPE_CODE_RETRIEVAL_ERROR', 'message': f'Error retrieving type code: {str(e)}'}, status=500)

    # 유형 코드가 없는 경우
    if not type_code:
        return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Invalid UUID or no type code found'}, status=404)

    # 유형 코드로 type_code_id를 가져오기
    try:
        # `type_code` 필드를 기준으로 검색
        type_code_obj = TypeCode.objects.get(type_code=type_code)
    except TypeCode.DoesNotExist:
        return JsonResponse({'error_code': 'TYPE_CODE_NOT_FOUND', 'message': 'Type code not found in database'}, status=404)
    except Exception as e:
        return JsonResponse({'error_code': 'TYPE_CODE_QUERY_ERROR', 'message': f'Error querying type code: {str(e)}'}, status=500)

    # type_code_id로 food_id들을 가져오기 (type_code_foods 테이블에서)
    try:
        # `type_code` 필드를 참조하여 food_id 가져오기
        food_ids = TypeCodeFood.objects.filter(type_code_id=type_code_obj).values_list('food_id', flat=True)
    except Exception as e:
        return JsonResponse({'error_code': 'FOOD_ID_RETRIEVAL_ERROR', 'message': f'Error retrieving food IDs: {str(e)}'}, status=500)

    # food_ids로 foods 테이블에서 food_name과 description을 가져오기
    try:
        # 음식 목록 조회 (food_name, description 포함)
        foods = Food.objects.filter(id__in=food_ids).values('id', 'food_name', 'description')
    except Exception as e:
        return JsonResponse({'error_code': 'FOODS_RETRIEVAL_ERROR', 'message': f'Error retrieving food details: {str(e)}'}, status=500)

    # 랜덤으로 3개 음식 선택
    try:
        # 랜덤으로 3개 음식 추출
        random_foods = random.sample(list(foods), min(len(foods), 3))  # 최대 3개 음식
        return JsonResponse({'random_foods': random_foods})
    except ValueError as e:
        return JsonResponse({'error_code': 'FOOD_SAMPLING_ERROR', 'message': f'Error sampling foods: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
