web: gunicorn ticketing_service.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A ticketing_service worker --loglevel=info --beat --concurrency=1
