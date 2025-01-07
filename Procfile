web: gunicorn wouldulike_backend.wsgi:application --log-file -

release: python manage.py migrate
web: gunicorn wouldulike_backend.wsgi:application --bind 0.0.0.0:$PORT --workers=2 --log-level=debug
