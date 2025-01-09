import random
from django.http import JsonResponse
from .models import FoodTasteType
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

    # 유형 코드로 음식 검색
    try:
        food_type = FoodTasteType.objects.get(type_code=type_code)
    except FoodTasteType.DoesNotExist:
        return JsonResponse({'error_code': 'TYPE_CODE_DOES_NOT_EXIST', 'message': 'Type code not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error_code': 'FOOD_TYPE_QUERY_ERROR', 'message': f'Error querying food type: {str(e)}'}, status=500)

    # 랜덤 음식 추출
    try:
        foods = food_type.foods
        random_foods = random.sample(foods, min(len(foods), 6))
        return JsonResponse({'random_foods': random_foods})
    except ValueError as e:
        return JsonResponse({'error_code': 'FOOD_SAMPLING_ERROR', 'message': f'Error sampling foods: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error_code': 'UNKNOWN_ERROR', 'message': f'Unexpected error: {str(e)}'}, status=500)
