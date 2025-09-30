FROM python:3.12

WORKDIR /app

# Установка системных зависимостей:
RUN apt-get update && apt-get install -y \
    nano \
    cron \
    supervisor \
    postgresql-client \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Добавление репозитория Microsoft для ODBC Driver 18:
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg \
    && mv microsoft.gpg /etc/apt/trusted.gpg.d/ \
    && curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements и установка Python пакетов:
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Копирование приложения:
COPY . .

# Создание директорий для логов:
RUN mkdir -p /app/logs /app/logs/supervisor /var/log/supervisor

# Копирование crontab файла:
COPY crontab /etc/cron.d/django-cron
RUN chmod 0644 /etc/cron.d/django-cron && crontab /etc/cron.d/django-cron

# Копирование конфигурации supervisor:
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Установка прав на entrypoint:
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]