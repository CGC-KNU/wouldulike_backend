"""
프론트엔드로 전달할 URL 설정 파일

여기를 수정하면 GET /api/url/ API 응답이 변경됩니다.
환경 변수 FRONTEND_URL로 오버라이드 가능.
"""
import os

# 프론트엔드로 전달할 URL (환경 변수 FRONTEND_URL로 오버라이드 가능)
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://open.kakao.com/o/s09ikE1h")
