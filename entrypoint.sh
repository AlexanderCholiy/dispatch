#!/bin/bash

# Функция для запуска management команд в фоне с перезапуском
start_management_command() {
    local command=$1
    
    while true; do
        echo "Starting $command..."
        python manage.py $command
        echo "$command stopped with exit code $?. Restarting in 10 seconds..."
        sleep 10
    done
}

# Функция ожидания доступности Postgres
wait_for_db() {
    echo "Waiting for database to be ready..."
    until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; do
        echo "Database is unavailable - sleeping 2s..."
        sleep 2
    done
    echo "Database is up and ready!"
}

# Функция инициализации приложения
init_app() {
    wait_for_db

    echo "Applying migrations..."
    python manage.py migrate --noinput

    echo "Creating default admin..."
    python manage.py add_default_admin --noinput

    echo "Adding default values..."
    python manage.py add_default_values --noinput

    echo "Collecting static..."
    python manage.py collectstatic --noinput
}

# Выполнить инициализацию приложения
init_app

# Запуск cron службы
echo "Starting cron service..."
service cron start

# Запуск непрерывных management команд в фоне
echo "Starting continuous management commands..."
start_management_command "parsing_emails" &
start_management_command "add_issues_2_yt" &
start_management_command "check_closed_yt_issues" &
start_management_command "check_unclosed_yt_issues" &

# Запуск Gunicorn
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 \
    --access-logfile /app/logs/gunicorn_access.log \
    --error-logfile /app/logs/gunicorn_error.log \
    backend.wsgi