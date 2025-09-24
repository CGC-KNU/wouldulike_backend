release: python manage.py migrate && python manage.py setup_admin_portal
web: gunicorn wouldulike_backend.wsgi:application --bind 0.0.0.0:$PORT --workers=2 --log-file - --log-level=info
