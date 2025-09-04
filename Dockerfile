FROM python:3.12

WORKDIR /app

# Установка системных зависимостей:
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python пакетов:
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Копирование приложения:
COPY . .

# Создание директорий для логов:
RUN mkdir -p /app/logs

# Копирование crontab файла:
COPY crontab /etc/cron.d/django-cron
RUN chmod 0644 /etc/cron.d/django-cron

# Установка прав на entrypoint:
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]