from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import PopupCampaign, Trend
from .serializers import PopupCampaignSerializer, TrendSerializer
from rest_framework.generics import RetrieveAPIView

class TrendListView(APIView):
    def get(self, request):
        trends = Trend.objects.all().order_by('-created_at')  # 최신순 정렬
        serializer = TrendSerializer(trends, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# id별로 트렌드 상세 정보를 반환하는 뷰
class TrendDetailView(RetrieveAPIView):
    queryset = Trend.objects.all()  # 모든 Trend 객체를 대상으로
    serializer_class = TrendSerializer  # Serializer 사용

    def get(self, request, pk):
        try:
            trend = Trend.objects.get(pk=pk)  # 주어진 id로 Trend 객체 가져오기
            serializer = TrendSerializer(trend)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Trend.DoesNotExist:
            return Response({"error": "Trend not found"}, status=status.HTTP_404_NOT_FOUND)


class PopupCampaignListView(APIView):
    def get(self, request):
        now = timezone.now()
        popup_campaigns = (
            PopupCampaign.objects.filter(
                is_active=True,
                start_at__lte=now,
                end_at__gte=now,
            )
            .order_by("display_order", "-created_at")
        )
        serializer = PopupCampaignSerializer(popup_campaigns, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PopupCampaignDetailView(RetrieveAPIView):
    queryset = PopupCampaign.objects.all()
    serializer_class = PopupCampaignSerializer

    def get(self, request, pk):
        try:
            popup_campaign = PopupCampaign.objects.get(pk=pk)
            serializer = PopupCampaignSerializer(popup_campaign)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except PopupCampaign.DoesNotExist:
            return Response(
                {"error": "Popup campaign not found"},
                status=status.HTTP_404_NOT_FOUND,
            )