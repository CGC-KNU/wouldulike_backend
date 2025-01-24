from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import TypeDescription
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def get_type_descriptions(request, type_code):
    # 설문조사 이후 유형 설명
    type_descriptions = get_object_or_404(TypeDescription, type_code=type_code)
    data = {
            "type_code": type_descriptions.type_code,
            "description": type_descriptions.description,
            # "image": type_descriptions.image,
            "created_at": type_descriptions.created_at,
            "updated_at": type_descriptions.updated_at,
        }
    return JsonResponse(data, safe=False)

@csrf_exempt
def get_all_type_descriptions(request, type_code):
    # 마이 유형 설명 (전체)
    type_descriptions = get_object_or_404(TypeDescription, type_code=type_code)
    data = {
        "type_code": type_descriptions.type_code,
        "type_name": type_descriptions.type_name,
        "description_detail": type_descriptions.description_detail, # 유형 설명
        "menu_and_mbti": type_descriptions.menu_and_mbti, # 어울리는 메뉴와 MBTI
        "meal_example": type_descriptions.meal_example, # 식사 경우 (예시)
        "matching_type": type_descriptions.matching_type, # 잘 어울리는 유형
        "non_matching_type": type_descriptions.non_matching_type, # 안 어울리는 유형
        "type_summary": type_descriptions.type_summary, # 유형 설명 종합
        "created_at": type_descriptions.created_at,
        "updated_at": type_descriptions.updated_at,
    }
    return JsonResponse(data, safe=False)