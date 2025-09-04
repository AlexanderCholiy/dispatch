#!/bin/bash
set -e

echo "Waiting for database..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
    echo "Database is unavailable - sleeping 2s..."
    sleep 2
done
echo "Database is ready!"

# Инициализация приложения
echo "Applying migrations and default data..."
python manage.py migrate --noinput &&
python manage.py add_default_admin --noinput &&
python manage.py add_default_values --noinput &&
python manage.py collectstatic --noinput

echo "Initialization complete. Starting supervisor..."
# Запуск supervisord, все процессы стартуют через supervisor
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf