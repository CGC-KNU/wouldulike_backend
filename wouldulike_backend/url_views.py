"""
URL을 프론트엔드로 전달하는 API 뷰
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .config_urls import FRONTEND_URL


class GetFrontendUrlView(APIView):
    """
    프론트엔드로 전달할 URL을 반환하는 API
    """
    
    def get(self, request):
        """
        GET 요청으로 URL을 반환합니다.
        
        Returns:
            Response: {
                "url": "전달할 URL (현재는 빈 문자열)"
            }
        """
        return Response(
            {
                "url": FRONTEND_URL
            },
            status=status.HTTP_200_OK
        )



