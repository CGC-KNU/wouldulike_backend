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
    # guests 앱에서 uuid를 사용해 유형 코드를 가져오는 로직
    type_code = get_type_code_from_uuid(user_uuid)

    if not type_code:
        return JsonResponse({'error': 'Invalid UUID or no type code found'}, status=404)

    # 유형 코드로 음식 검색
    try:
        food_type = FoodTasteType.objects.get(type_code=type_code)
        foods = food_type.foods
        random_foods = random.sample(foods, min(len(foods), 6))
        return JsonResponse({'random_foods': random_foods})
    except FoodTasteType.DoesNotExist:
        return JsonResponse({'error': 'Type code not found'}, status=404)
