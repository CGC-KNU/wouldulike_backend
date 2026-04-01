"""
테스트 실행 전용 설정.

- 로컬/CI 환경에서 Pillow 등 OS 의존 패키지 없이도 핵심 로직 테스트를 돌릴 수 있도록
  ImageField를 사용하는 앱을 INSTALLED_APPS에서 제외합니다.
"""

from .settings import *  # noqa: F403


# Pillow 미설치 환경에서 Django system check가 실패하는 것을 방지하기 위해 trends 앱을 제외
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "trends"]  # noqa: F405

# URLConf도 trends를 import하지 않도록 테스트 전용으로 교체
ROOT_URLCONF = "wouldulike_backend.test_urls"

