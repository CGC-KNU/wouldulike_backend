release: python manage.py migrate && python manage.py setup_admin_portal
web: gunicorn wouldulike_backend.wsgi:application --bind 0.0.0.0:$PORT --workers=10 --timeout=120 --graceful-timeout=30 --max-requests=500 --max-requests-jitter=50 --preload --log-file - --log-level=info
