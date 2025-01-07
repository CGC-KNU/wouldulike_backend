from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Trend
from .serializers import TrendSerializer
from rest_framework.generics import RetrieveAPIView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
# import logging

@method_decorator(csrf_exempt, name='dispatch')
class TrendListView(APIView):
    def get(self, request):
        trends = Trend.objects.all().order_by('-created_at')  # 최신순 정렬
        serializer = TrendSerializer(trends, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# id별로 트렌드 상세 정보를 반환하는 뷰
class TrendDetailView(RetrieveAPIView):
    queryset = Trend.objects.all()  # 모든 Trend 객체를 대상으로
    serializer_class = TrendSerializer  # Serializer 사용

    # def get(self, request, pk):
    #     try:
    #         trend = Trend.objects.get(pk=pk)  # 주어진 id로 Trend 객체 가져오기
    #         serializer = TrendSerializer(trend)
    #         return Response(serializer.data, status=status.HTTP_200_OK)
    #     except Trend.DoesNotExist:
    #         return Response({"error": "Trend not found"}, status=status.HTTP_404_NOT_FOUND)
    #     except Exception as e:
    #         logging.error(f"Server error: {str(e)}")
    #         return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)