"""
팝업 캠페인 전체 삭제 management command.

사용 예:
  python manage.py delete_popup_campaigns --force
"""

from django.core.management.base import BaseCommand, CommandError

from trends.models import PopupCampaign


class Command(BaseCommand):
    help = "저장된 팝업 캠페인(PopupCampaign) 데이터를 모두 삭제합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="실제로 삭제를 수행합니다. (미지정 시 삭제하지 않음)",
        )

    def handle(self, *args, **options):
        if not options["force"]:
            raise CommandError("삭제를 수행하려면 --force 옵션이 필요합니다.")

        count = PopupCampaign.objects.count()
        deleted, _ = PopupCampaign.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"팝업 캠페인 전체 삭제 완료: 대상 {count}건, 삭제 {deleted}건"
            )
        )
