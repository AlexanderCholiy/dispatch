<h1 align="center">DISPATCH</h1>

**DISPATCH** — это микросервис для диспетчерской службы, интегрированный с электронной почтой и сервисом Yandex Tracker.
В дальнейшем его можно расширить до полноценной самостоятельной системы управления инцидентами.

<p align="center">
  <img src=".github/images/yandex_tracker/interface/issues_list.png" alt="Список задач" width="500">
  <img src=".github/images/yandex_tracker/interface/issue_detail.png" alt="Пример задачи" width="500">
</p>

---

## 📑 Оглавление

1. [Основные возможности](#1-Основные возможности)  
2. [Настройка очереди](#2-настройка-очереди)  
3. [Интеграция с почтой](#3-интеграция-с-почтой)  
4. [Глобальные поля](#4-глобальные-поля)  
5. [Локальные поля](#5-локальные-поля)  

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

### ✉️ Автоответы
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

| Категория          | Технологии                                 |
|--------------------|--------------------------------------------|
| **Backend**        | Python 3.12, Django 4.2, YandexTracker API |
| **Frontend**       | Веб-интерфейс через Yandex Tracker         |
| **База данных**    | PostgreSQL                                 |
| **Инфраструктура** | Docker, Docker Compose, Nginx              |
| **CI/CD**          | GitHub Actions                             |

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
  <img src=".github/images/yandex_tracker/fields/global/avr_name.png" alt="Имя подрядчика" width="500">
  <img src=".github/images/yandex_tracker/fields/global/base_station_number.png" alt="Номер базовой станции" width="500">
  <img src=".github/images/yandex_tracker/fields/global/email_comments_ids.png" alt="ID писем, добавленных в комментарии" width="500">
  <img src=".github/images/yandex_tracker/fields/global/incident_date.png" alt="Дата регистрации инцидента" width="500">
  <img src=".github/images/yandex_tracker/fields/global/incident_id.png" alt="ID инцидента" width="500">
  <img src=".github/images/yandex_tracker/fields/global/is_new_msg.png" alt="Флаг нового письма" width="500">
  <img src=".github/images/yandex_tracker/fields/global/operator.png" alt="Оператор базовой станции" width="500">
  <img src=".github/images/yandex_tracker/fields/global/pole_number.png" alt="Шифр опоры" width="500">
  <img src=".github/images/yandex_tracker/fields/global/sla_deadline.png" alt="Дедлайн SLA" width="500">
  <img src=".github/images/yandex_tracker/fields/global/sla_status.png" alt="Статус SLA" width="500">
</p>  

### 5. Локальные поля
Перейдите: *Очереди → Имя очереди → Настройки очереди → Локальные поля* и создайте новые (ключи понадобятся в дальнейшем):  
<p align="center">
  <img src=".github/images/yandex_tracker/fields/local/type_of_problem.png" alt="Тип проблемы" width="500">
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
DJANGO_ALLOWED_HOSTS=ip_сервера, 127.0.0.1
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

        location / {
            proxy_set_header Host $http_host;
            proxy_pass http://127.0.0.1:8000;
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

sudo docker compose stop && sudo docker compose up --build -d

sudo docker compose exec dispatch_backend bash



### Запуск в режиме разработки
Запустите из докер compose только базу данных PostgreSQL
sudo docker compose up -d dispatch_db

в .env файле выставите DEBUG=True
3. Установите и активируйте виртуальное окружение и зависимости
```
python3.9 -m venv venv
```
> Установка виртуального окружения (версия python 3.12).
```
. .\venv\Scripts\activate
```
> Активация виртуального окружения для Windows.
```
. ./venv/bin/activate
```
> Активация виртуального окружения для Linux или MacOS.
```
pip install -r requirements.txt
```
> Установка зависимостей.







Полезные команды:
сброс индексации id в таблицах emails_emailmessage и incidents_incident если заново запускаем базу данных:
ALTER SEQUENCE public.emails_emailmessage_id_seq RESTART WITH 10000;
ALTER SEQUENCE public.incidents_incident_id_seq RESTART WITH 10000;


sudo docker ps -a


Кол-во ядер (нужно для настройки gunicorn)
lscpu | grep "^CPU(s):"

Кол-во потоков (нужно для настройки gunicorn)
lscpu | grep "Thread(s) per core"

Формула для workers:
workers = 2 * CPU + 1

Кол-во оперативной памяти:
free -h

## 🛠️ Полезные команды
Команды для управления контейнерами, проверки стиля кода и установки зависимостей:
### Docker
```
sudo docker compose stop
```
> Остановка всех контейнеров, указанных в docker-compose.yml
```
sudo docker container prune -f
```
> Удалить все остановленные контейнеры
```
sudo docker image prune -f
```
> Удалить все неиспользуемые образы

### Проверка стиля кода
```
python -m flake8
```
> Проверка соответствия PEP8
```
isort .
```
> Автоматическая сортировка импортов

### Установка зависимостей
```
pip install <имя_библиотеки> --no-deps
```
> Используйте флаг --no-deps, чтобы избежать автоматической установки зависимостей, которые могут конфликтовать с текущими версиями библиотек, особенно с Django.
> Это особенно важно, так как для работы с MongoDB используется djongo, который требует строго определённую версию Django (например, Django 3.2), и автоматическая установка может её перезаписать.

### Переустановить подключение через VS Code
```
cd ~ && rm -rf ~/.vscode-server
```
> Удалить всю директорию .vscode-server из домашней папки

---

## Автор
**Чолий Александр** ([Telegram](https://t.me/alexander_choliy))
