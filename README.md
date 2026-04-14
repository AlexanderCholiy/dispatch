<h1 align="center">DISPATCH</h1>

**DISPATCH** — это микросервис для диспетчерской службы, интегрированный с электронной почтой и сервисом Yandex Tracker.
В дальнейшем его можно расширить до полноценной самостоятельной системы управления инцидентами.

<p align="center">
  <img src=".github/images/yandex_tracker/interface/issues_list.png" alt="Список задач" width="500">
  <img src=".github/images/yandex_tracker/interface/issue_detail.png" alt="Пример задачи" width="500">
</p>

---

## 📑 Оглавление

1. [Основные возможности](#-основные-возможности)
   1. [Синхронизация с Yandex Tracker](#-синхронизация-с-yandex-tracker)
   2. [Автоответы](#autoanswers)
   3. [SLA-контроль](#-sla-контроль)
   4. [Работа с почтой](#-работа-с-почтой)
3. [API](#-api)  
4. [Архитектура и контейнеры](#-архитектура-и-контейнеры)  
5. [Стек технологий](#-стек-технологий)  
6. [Интеграция с API YandexTracker](#-интеграция-с-api-yandextracker)  
   1. [Регистрация и доступы](#1-регистрация-и-доступы)  
   2. [Настройка очереди](#2-настройка-очереди)  
   3. [Интеграция с почтой](#3-интеграция-с-почтой)  
   4. [Глобальные поля](#4-глобальные-поля)  
   5. [Локальные поля](#5-локальные-поля)  
7. [Установка и запуск проекта в Docker](#-установка-и-запуск-проекта-в-docker)  
8. [Запуск в режиме разработки](#-запуск-в-режиме-разработки)  
9. [Полезные команды](#-полезные-команды)  
   1. [Работа с базой данных](#1-работа-с-базой-данных)  
   2. [Работа с Docker](#2-работа-с-docker)  
   3. [Настройка Gunicorn](#3-настройка-gunicorn)  
   4. [Проверка стиля кода](#4-проверка-стиля-кода)  
   5. [Управление зависимостями](#5-управление-зависимостями)  
   6. [Переустановить подключение через VS Code](#6-переустановить-подключение-через-vs-code)  
10. [Автор](#-автор)

---

## 📌 Основные возможности

- Чтение входящих и исходящих писем из почты.

- Автоматическое создание инцидентов в базе данных на основании писем.

- Назначение инцидента самому свободному диспетчеру, зарегистрированному в системе и в трекере.

- Поиск и привязка опоры и/или базовой станции из текста письма или переписки.

- Автоматическая постановка задач в Yandex Tracker через API:

- Добавление ответов на письма как комментариев к задаче.

### 🔄 Синхронизация с Yandex Tracker
Регулярный обмен данными с YT для поддержания актуальности статусов.

Если диспетчер укажет шифр опоры — система автоматически подтянет подрядчика.

Если указать номер базовой станции — система по возможности подтянет шифр опоры и оператора.

При вводе невалидных данных задача получает статус **Ошибка**, а в комментарии указывается причина.

<h3 id="autoanswers">✉️ Автоответы</h3>
Передать в работу подрядчику → формируется и отправляется шаблонное письмо подрядчику.

Уведомить оператора → отправляется письмо заявителю о принятии заявки в работу.

Уведомить о закрытии → отправляется письмо заявителю о завершении инцидента.

### ⏰ SLA-контроль
Точка отсчёта SLA зависит от способа создания инцидента:

по письму → дата/время первого письма,

вручную в трекере → дата создания задачи.

После выбора типа проблемы в интерфейсе трекера рассчитывается дедлайн SLA и отображается его статус.

### 📬 Работа с почтой
Для идентификации переписок в первую очередь используются заголовки письма: **In-Reply-To**, **Message-ID** и **References**.
Если же определить инцидент по ним не удалось, в качестве резервного варианта применяется код инцидента в теме письма. Таким образом, к одному инциденту может быть привязано сразу несколько независимых переписок.

Особенность работы Yandex Tracker в том, что при отправке писем они уходят как новые сообщения. Поэтому важно:

1. Указывать код инцидента в теме письма.

2. Добавлять в копию адрес почты, с которого собираются инциденты.

Благодаря этому цепочка переписки сохранится даже в случае, если получатель изменит тему письма.

---

### 📡 API
Проект предоставляет REST API для работы с инцидентами.
1. Эндпоинт:
   ```
   GET /api/v1/report/incidents/
   ```
   > Возвращает подробную информацию по инцидентам с пагинацией.
   ```
   GET /api/v1/report/incidents/?all=true
   ```
   > Возвращает подробную информацию по инцидентам без пагинации.
  **Особенности**:
   - Доступна фильтрация по дате инцидента:
    ```
    GET /api/v1/report/incidents/?incident_date_after=2025-10-12&incident_date_before=2025-10-15
    ```
    > Получить инциденты за определенный период
    ```
    GET /api/v1/report/incidents/?last_month=true
    ```
    > Получить инциденты с первого числа предыдущего месяца по текущее число.    
   - Чтение доступно всем пользователям.
  **Возвращаемые поля**:
    - `id` — ID инцидента
    - `code` — код инцидента, который добавляется в тему ответных писем 
    - `last_status` — последний статус инцидента
    - `incident_type` — тип инцидента
    - `categories` - категории инцидента
    - `is_auto_incident` — способ регистрации (автоматически через почту или вручную через диспетчера)
    - `is_incident_finish` — завершен ли инцидент
    - `incident_datetime` — дата и время регистрации
    - `incident_finish_datetime` — дата и время завершения
    - `is_transfer_to_avr` — передано ли в АВР
    - `avr_start_datetime' — дата и время передачи АВР
    - `avr_end_datetime` — дата и время завершения АВР
    - `is_vendor_sla_avr_expired` — просрочен ли SLA АВР
    - `vendor_avr_deadline` — дедлайн АВР
    - `avr_vendor` — имя подрядчика по АВР
    - `avr_vendor_emails` — email подрядичика по АВР
    - `is_transfer_to_rvr` — передано ли в РВР
    - `rvr_start_datetime` — дата и время передачи РВР
    - `rvr_end_datetime` — дата и время завершения РВР
    - `is_vendor_sla_rvr_expired` — просрочен ли SLA РВР
    - `vendor_rvr_deadline` — дата и время завершения РВР
    - `pole` — шифр опоры
    - `region_ru` — регион
    - `address` — адрес
    - `pole_latitude` — широта опоры
    - `pole_longtitude` — долгота опоры
    - `base_station` — номер базовой станции
    - `operator_group` — группа операторов
    - `operators` — операторы

---

## ⚙️ Архитектура и контейнеры

Проект запускается в Docker и состоит из трёх контейнеров:

- **dispatch_db** — PostgreSQL.

- **dispatch_gateway** — Nginx (конфиг: gateway/nginx.conf).

- **dispatch_backend** — Django-приложение (запуск через Supervisor).

Supervisor управляет запуском:

- инициализации Django (миграции, создание администратора, сбор статики, загрузка дефолтных данных);

- cron-задач:
  - резервное копирование базы данных,

  - синхронизация данных с TowerStore,

  - очистка неактуальных записей в БД;

- парсинга входящих и исходящих писем;

- синхронизации с Yandex Tracker (открытие/закрытие задач, SLA-контроль, автодействия);

- Gunicorn (по умолчанию: 9 workers × 2 threads) для запуска веб-интерфейса.


---

## 🧩 Стек технологий

| Категория          | Технологии                                                   |
|--------------------|--------------------------------------------------------------|
| **Backend**        | Python 3.12, Django 4.2, YandexTracker API, Celery, RabbitMQ |
| **Frontend**       | Веб-интерфейс через Django Templates, Yandex Tracker         |
| **База данных**    | PostgreSQL, Redis                                            |
| **Инфраструктура** | Docker, Docker Compose, Nginx                                |
| **CI/CD**          | GitHub Actions                                               |

---

## 🔗 Интеграция с API YandexTracker

### 1. Регистрация и доступы
1. Зарегистрируйтесь в [Yandex Tracker](https://tracker.yandex.ru/hi-there/create).  
2. Создайте приложение в **OAuth Яндекс** и получите **Client ID** и **Client Secret**.  
3. Сгенерируйте **OAuth-токен** для работы с API.  
4. В интерфейсе Tracker откройте: *Администрирование → Организации* и сохраните **идентификатор организации**.  

### 2. Настройка очереди
Перейдите: *Очереди → Имя вашей очереди → Настройки очереди*.  

1. Создайте и настройте **рабочий процесс**, как на примере:  
   <p align="center">
     <img src=".github/images/yandex_tracker/work_process/incident_work_process.png" alt="Рабочий процесс инцидента" width="800">
     <img src=".github/images/yandex_tracker/work_process/detail_work_process.png" alt="Переходы в рабочем процессе" width="800">
   </p>

   > Рабочий процесс должен начинаться со статуса **Новый**.  

2. Добавьте дополнительные статусы (ключи понадобятся в дальнейшем):  
   <p align="center">
     <img src=".github/images/yandex_tracker/statuses/statuses_part_1.png" alt="Автодействия" width="500">
   </p>
   <p align="center">
     <img src=".github/images/yandex_tracker/statuses/statuses_part_2.png" alt="На генерации" width="500">
   </p>

### 3. Интеграция с почтой
По умолчанию Yandex Tracker использует папку *INBOX*, после чего письма помечаются как прочитанные и перемещаются в архив. Это поведение нежелательно.  

Чтобы сохранить возможность отправки писем из интерфейса Tracker:  
- создайте в почте папки:  
  - `YandexTrackerInbox`  
  - `YandexTrackerArchive`  
- укажите их в настройках очереди:  
  *Очереди → Имя очереди → Настройки очереди → Интеграции*  

Пример настроек:  
<p align="center">
  <img src=".github/images/yandex_tracker/email_setup/default_settings.png" alt="Интеграция с почтой" width="500">
</p>  
<p align="center">
  <img src=".github/images/yandex_tracker/email_setup/integrations_part_1.png" alt="Получение писем" width="500">
</p>
<p align="center">
  <img src=".github/images/yandex_tracker/email_setup/integrations_part_2.png" alt="Параметры задач" width="500">
</p>
<p align="center">
  <img src=".github/images/yandex_tracker/email_setup/integrations_part_3.png" alt="Отправка ответов" width="500">
</p>  

---

### 4. Глобальные поля
В разделе *Администрирование → Поля* создайте следующие глобальные поля (ключи понадобятся в дальнейшем):  
<p align="center">
  <img src=".github/images/yandex_tracker/fields/global/avr_name.png" alt="Имя подрядчика" width="300">
  <img src=".github/images/yandex_tracker/fields/global/base_station_number.png" alt="Номер базовой станции" width="300">
  <img src=".github/images/yandex_tracker/fields/global/email_comments_ids.png" alt="ID писем, добавленных в комментарии" width="300">
  <img src=".github/images/yandex_tracker/fields/global/incident_date.png" alt="Дата регистрации инцидента" width="300">
  <img src=".github/images/yandex_tracker/fields/global/incident_id.png" alt="ID инцидента" width="300">
  <img src=".github/images/yandex_tracker/fields/global/is_new_msg.png" alt="Флаг нового письма" width="300">
  <img src=".github/images/yandex_tracker/fields/global/operator.png" alt="Оператор базовой станции" width="300">
  <img src=".github/images/yandex_tracker/fields/global/pole_number.png" alt="Шифр опоры" width="300">
  <img src=".github/images/yandex_tracker/fields/global/sla_deadline.png" alt="Дедлайн SLA" width="300">
  <img src=".github/images/yandex_tracker/fields/global/sla_status.png" alt="Статус SLA" width="300">
  <img src=".github/images/yandex_tracker/fields/global/monitoring.png" alt="Мониторинг" width="300">
</p>  

### 5. Локальные поля
Перейдите: *Очереди → Имя очереди → Настройки очереди → Локальные поля* и создайте новые (ключи понадобятся в дальнейшем):  
<p align="center">
  <img src=".github/images/yandex_tracker/fields/local/type_of_problem.png" alt="Тип проблемы" width="300">
</p>  

> Убедитесь, что значения поля *Тип проблемы* совпадают с используемыми в вашей системе.  

Поздравляю, минимальная настройка **Yandex Tracker** завершена.

---

## 🚀 Установка и запуск проекта в Docker

### 1. Подготовка окружения
1. Клонируйте репозиторий на сервер:
```bash
git clone https://github.com/AlexanderCholiy/dispatch.git
cd dispatch
```
2. Создайте файл `.env` со следующими переменными окружения:
```
# Django
SECRET_KEY=ключ_для_django
DJANGO_ALLOWED_HOSTS=ip_сервера, 127.0.0.1, доменное_имя
CSRF_TRUSTED_ORIGINS=https://доменное_имя, https://ip_сервера
DEBUG=False
EMAIL_HOST=SMTP_хост
EMAIL_HOST_USER=email_для_приложения
EMAIL_HOST_PASSWORD=пароль_почты
EMAIL_PORT=587
EMAIL_USE_TLS=True

# Default User
ADMIN_USERNAME=админ_логин
ADMIN_EMAIL=админ_email
ADMIN_PASSWORD=админ_пароль

# Database
DB_HOST=dispatch_db
DB_PORT=5432
POSTGRES_DB=XXXX
POSTGRES_USER=XXXX
POSTGRES_PASSWORD=XXXX

# База данных мониторинга (только для чтения)
MONITORING_DB_NAME=XXXX
MONITORING_DB_USER=XXXX
MONITORING_DB_PASSWORD=XXXX
MONITORING_DB_HOST=XXXX
MONITORING_DB_PORT=XXXX

# API TowerStore
TS_POLES_TL_URL=url_с_данными_по_опоры
TS_AVR_REPORT_URL=url_с_данными_по_подрядчика_подрядчика
TS_BS_REPORT_URL=url_с_данными_по_базовым_станциям_и_операторам

# Default Contractors
DEFAULT_CONTRACTOR_EMAILS=список_почт_через_запятую

# Email для инцидентов
PARSING_EMAIL_LOGIN=email_для_парсинга
PARSING_EMAIL_PSWD=пароль
PARSING_EMAIL_SERVER=imap.хост
PARSING_EMAIL_PORT=993
# Имя папки ВХОДЯЩИЕ:
PARSING_EMAIL_SENT_FOLDER_NAME=&BB4EQgQ,BEAEMAQyBDsENQQ9BD0ESwQ1

# YandexTracker (доступы)
YT_CLIENT_ID=...
YT_CLIENT_SECRET=...
YT_ORGANIZATION_ID=...
YT_ACCESS_TOKEN=...
YT_REFRESH_TOKEN=...

# YandexTracker (очередь и поля)
YT_QUEUE=имя_очереди
YT_DATABASE_ID_GLOBAL_FIELD_ID=...
YT_EMAILS_IDS_GLOBAL_FIELD_ID=...
YT_POLE_NUMBER_GLOBAL_FIELD_ID=...
YT_BASE_STATION_GLOBAL_FIELD_ID=...
YT_EMAIL_DATETIME_GLOBAL_FIELD_ID=...
YT_IS_NEW_MSG_GLOBAL_FIELD_ID=...
YT_SLA_DEADLINE_GLOBAL_FIELD_ID=...
YT_IS_SLA_EXPIRED_GLOBAL_FIELD_ID=...
YT_OPERATOR_NAME_GLOBAL_FIELD_NAME=...
YT_AVR_NAME_GLOBAL_FIELD_ID=...
YT_MONITORING_GLOBAL_FIELD_ID=...
YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID=...

# YandexTracker (кастомные статусы)
YT_ON_GENERATION_STATUS_KEY=...
YT_NOTIFY_OPERATOR_ISSUE_IN_WORK_STATUS_KEY=...
YT_NOTIFIED_OPERATOR_ISSUE_IN_WORK_STATUS_KEY=...
YT_NOTIFY_OPERATOR_ISSUE_CLOSED_STATUS_KEY=...
YT_NOTIFIED_OPERATOR_ISSUE_CLOSED_STATUS_KEY=...
YT_NOTIFY_AVR_CONTRACTOR_IN_WORK_STATUS_KEY=...
YT_NOTIFIED_AVR_CONTRACTOR_IN_WORK_STATUS_KEY=...

# Telegram
TG_TOKEN=...
TG_DEFAULT_USER_ID=...
```

### 2. Установка Docker и Docker Compose (Ubuntu)
1. Обновите пакеты и установите зависимости:
```bash
sudo apt update && sudo apt install ca-certificates curl
```
2. Добавьте GPG-ключ и репозиторий Docker:
```bash
sudo install -m 0755 -d /etc/apt/keyrings
```
```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
```
```bash
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```
3. Установите Docker:
```bash
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
4. Проверьте работу Docker:
```bash
sudo systemctl status docker 
```

⚠️ Обратите внимание:
- логи пишутся в папку ./logs, которой нужно выдать права:
```bash
sudo chmod -R 777 ./logs
```

- данные (папка ./data) также требуют прав:
```bash
sudo chmod -R 777 ./data
```

- .env примонтирован внутрь контейнера.

- база данных и media файлы хранятся в Docker volumes.

### 3. Сборка и запуск контейнеров
1. Загрузите/обновите образы из Docker Hub:
```bash
sudo docker compose -f docker-compose.production.yml pull
```
2. Перезапустите сервисы:
```bash
sudo docker compose -f docker-compose.production.yml down
```
```bash
sudo docker compose -f docker-compose.production.yml up -d
```


### 4. Настройка Nginx
1. Отредактируйте файл `/etc/nginx/sites-enabled/default`, добавив минимально необходимую конфигурацию:
```
server {
        listen 80;
        server_name _;

        client_max_body_size 50M;

        location / {
            proxy_set_header Host $http_host;
            proxy_pass http://<ваш_ip_адрес>:8000;
  
            # WebSocket:
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }

}
```
2. Проверьте и примените конфигурацию:
```bash
sudo nginx -t
```
```bash
sudo service nginx reload
```

✅ Готово!
Приложение будет доступно по адресу: `http(s)://<хост_сервера>/`

---

## ⚙️ Запуск в режиме разработки
1. Запустите необходимые контейнеры через Docker Compose: базу данных PostgreSQL, Redis, брокер сообщений RabbitMQ и воркеры Celery для фоновой обработки задач:
```bash
sudo docker compose up -d --build --force-recreate dispatch_db dispatch_redis dispatch_rabbitmq dispatch_celery_heavy_worker dispatch_celery_worker dispatch_celery_beat
```
```bash
sudo docker compose restart dispatch_celery_heavy_worker dispatch_celery_worker dispatch_celery_beat
```
> Если вы изменяете код задач Celery, обязательно перезапускайте соответствующие сервисы, чтобы новые изменения вступили в силу.

2. В файле .env установите флаг отладки `DEBUG=True`.

3. Создайте и активируйте виртуальное окружение, затем установите зависимости:
```bash
python3.12 -m venv venv
```
> Установка виртуального окружения (версия python 3.12).
```bash
. .\venv\Scripts\activate
```
> Активация виртуального окружения для Windows.
```bash
. ./venv/bin/activate
```
> Активация виртуального окружения для Linux или MacOS.
```bash
pip install -r requirements.txt
```
> Установка зависимостей.
sudo apt-get install -y curl

4. Установите Microsoft ODBC 17 Driver for SQL Server (Linux):
```bash
sudo apt-get install -y curl
```
> Установка утилиты для передачи данных по различным сетевым протоколам
```bash
sudo rm -f /etc/apt/sources.list.d/mssql-release.list
```
> Удаляем возможные некорректные файлы
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg
```
> Импорт ключа Microsoft
```bash
sudo curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list -o /etc/apt/sources.list.d/mssql-release.list
```
> Добавление репозитория Microsoft (замени '22.04' на твою версию Ubuntu)
> 
> Microsoft пока не выпускает полноценную поддержку Ubuntu 24.04 (noble). Если выше не работает, проще перейти на Ubuntu 22.04
```bash
sudo apt-get update --allow-unauthenticated
```
> Обновляем пакеты
```bash
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc unixodbc-dev
```
> Установка драйвера ODBC 17 и unixODBC
> 
> В Linux 24.04 ODBC Driver 18 иногда вызывает проблемы с SSL-соединением, особенно при работе с серверами MSSQL, использующими самоподписанные сертификаты.

5. Проверка работы WebSocke:
```bash
uvicorn backend.asgi:application --reload
```
> Запуск приложения с автоматической перезагрузкой, но без раздачи статики.

---

## 🛠️ Полезные команды
### 1. Работа с базой данных
```
ALTER SEQUENCE public.emails_emailmessage_id_seq RESTART WITH 10000;
ALTER SEQUENCE public.incidents_incident_id_seq RESTART WITH 10000;
```
> Сброс автоинкремента ID в таблицах emails_emailmessage и incidents_incident (например, при пересоздании базы).

### 2. Работа с Docker
```bash
sudo docker ps -a
```
> Просмотр всех контейнеров (включая остановленные).
```bash
sudo docker compose stop
```
> Остановка всех контейнеров, указанных в docker-compose.yml.
```bash
sudo docker container prune -f
```
> Удалить все остановленные контейнеры.
```bash
sudo docker image prune -f
```
> Удалить все неиспользуемые образы.
```bash
sudo docker compose exec dispatch_backend bash
```
> Открыть терминал контейнера с приложением.
```bash
sudo docker compose stop && sudo docker compose up --build -d
```
> Локально пересобрать и запустить докер образы.
```bash
sudo docker compose build dispatch_gateway && sudo docker compose up -d dispatch_gateway
```
> Локально пересобрать и перезапустить докер образ nginx.

### 3. Настройка Gunicorn
1. Определение ресурсов сервера:
```bash
lscpu | grep "^CPU(s):"
```
> Количество ядер процессора.
```bash
lscpu | grep "Thread(s) per core"
```
> Количество потоков на ядро.
```bash
free -h
```
> Проверка объёма оперативной памяти.
```bash
lsb_release -a
```
> Узнать версию Ubuntu.
Формула расчёта числа воркеров: `workers = 2 * CPU + 1`

### 4. Проверка стиля кода
```bash
python -m flake8
```
> Проверка соответствия кода стандартам PEP8.
```bash
isort .
```
> Автоматическая сортировка импортов

### 5. Управление зависимостями
```bash
pip install <имя_библиотеки> --no-deps
```
> Используйте флаг --no-deps, чтобы избежать автоматической установки зависимостей, которые могут конфликтовать с текущими версиями библиотек, особенно с Django.

### 6. Запуск ASGI приложения в режиме разработки
```bash
daphne backend.asgi:application
```
> Необходимо для работы Web Socket, однако статика не подключается и тестировать не удобно.

### 7. Переустановить подключение через VS Code
```bash
cd ~ && rm -rf ~/.vscode-server
```
> Полное удаление директории .vscode-server из домашней папки (помогает при проблемах с подключением).

---

## 👋 Автор
**Чолий Александр** ([Telegram](https://t.me/alexander_choliy))
