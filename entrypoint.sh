#!/bin/bash
set -e

echo "Oczekiwanie na PostgreSQL..."
until python -c "
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        host=os.environ['POSTGRES_HOST'],
        port=os.environ['POSTGRES_PORT']
    )
    sys.exit(0)
except Exception as e:
    print(e)
    sys.exit(1)
"; do
    echo "PostgreSQL niedostępny – czekam 2s..."
    sleep 2
done

echo "PostgreSQL gotowy!"

if [ $# -eq 0 ]; then
    python manage.py migrate --noinput
    exec python manage.py runserver 0.0.0.0:8000
else
    exec "$@"
fi
