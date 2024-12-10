from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Trend
from .serializers import TrendSerializer

class TrendListView(APIView):
    def get(self, request):
        trends = Trend.objects.all().order_by('-created_at')  # 최신순 정렬
        serializer = TrendSerializer(trends, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
