"""
URL을 프론트엔드로 전달하는 API 뷰
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .config_urls import FRONTEND_URL


class GetFrontendUrlView(APIView):
    """
    프론트엔드로 전달할 URL을 반환하는 API

    config_urls.py의 FRONTEND_URL을 수정하면 여기서 반환되는 값이 변경됩니다.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"url": FRONTEND_URL}, status=status.HTTP_200_OK)



