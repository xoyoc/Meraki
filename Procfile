web: gunicorn --bind 0.0.0.0:$PORT sistema.wsgi:application
release: python manage.py collectstatic --noinput && python manage.py migrate
