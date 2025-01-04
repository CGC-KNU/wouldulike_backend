from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import TypeDescription

def get_type_descriptions(request, type_code):
    # 유형 코드를 기반으로 데이터를 가져옴
    type_descriptions = get_object_or_404(TypeDescription, type_code=type_code)
    data = {
            "type_code": type_descriptions.type_code,
            "description": type_descriptions.description,
            # "image": type_descriptions.image,
            "created_at": type_descriptions.created_at,
            "updated_at": type_descriptions.updated_at,
        }
    return JsonResponse(data, safe=False)
