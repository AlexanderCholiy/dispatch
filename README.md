<h1 align="center">DISPATCH</h1>

**DISPATCH** — это микросервис для диспетчерской службы, интегрированный с электронной почтой и сервисом Yandex Tracker.
В дальнейшем его можно расширить до полноценной самостоятельной системы управления инцидентами.

<p align="center">
  <img src=".github/images/yandex_tracker/interface/issues_list.png" alt="Список задач" width="500">
  <img src=".github/images/yandex_tracker/issue_detail.png" alt="Пример задачи" width="500">
</p>

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

⚙️ Архитектура и контейнеры

Проект запускается в Docker и состоит из трёх контейнеров:

dispatch_db — PostgreSQL.

dispatch_gateway — Nginx (конфиг: gateway/nginx.conf).

dispatch_backend — Django-приложение (запуск через Supervisor).

Supervisor запускает:

инициализацию Django (миграции, админ, статика, дефолтные данные),

cron-задачи,

парсинг входящих и исходящих писем,

синхронизацию с Yandex Tracker (открытые/закрытые задачи, SLA, автодействия),

gunicorn (по умолчанию: 9 workers, 2 threads).


## 🧩 Стек технологий:
| Категория          | Технологии                          |
|--------------------|-------------------------------------|
| **Backend**        | Python 3.12, Django 4.2, YandexTracker API                  |
| **Frontend**       | YandexTracker (интерфейс)           |
| **База данных**    | PostgreSQL                 |
| **Инфраструктура** | Docker, Docker Compose, Nginx       |
| **CI/CD**          | GitHub Actions                      |



Интеграция с API YandexTracker:

1. Зарегестрируйтесь в YandexTracker: https://tracker.yandex.ru/hi-there/create

2. Получите Client ID и Client Secret для интеграции с Яндекс Трекером, перейдите на страницу создания приложения в OAuth Яндекс.

3. Получите OAuth-токен, который можно использовать для работы с API Яндекс Трекера.

4. В YandexTracker перейдите в панель Администратирование -> Организации и сохраните идентификатор организации.

Настройка очереди YandexTracker:
Перейдите в очередь -> настройки очереди

1. Настройте рабочий процесс в очереди как на картинке:

2. Настройте интеграцию с почтой YandexTracker, чтобы можно было отправлять письма прямо из интерфейса трекера перейдите во вкладку интерграции.
   Включите возможность отправки писем наружу, а также добавлять номер задачи в тему письма. Далее перейдите в настройки почтового ящика и добавьте почту с которой должны приходить все заявки.
   Внимание, yanex tracker по умолчанию использует папку ВХОДЯЩИЕ для сбора писем м формирования по ним задач. В итоге все письма будут помечаться как прочитанные, а также перемещаться в архивную папку.
   Такое поведение не допустимо, к тому же в дальнейшем планируется переход из YandexTracker на свою систему, поэтому мы используем свой парсер почты. Однако чтобы можно было отправлять письма из трекера мы просто в почте создадим две папки
   YandexTrackerInbox и YandexTrackerArchive, которые потом укажем в YandexTracker.

3. В YandexTracker необходимо добавить новые глобальные и локальные поля как на картинках ниже:


Поздравляю минимальная настройка YandexTracker завершшена.



## 🚀 Установка и запуск проекта в Docker

### Подготовка окружения
1. Создайте склонируйте репозиторий к себе на сервер:
```
git clone https://github.com/AlexanderCholiy/dispatch.git
```
2. Создайте файл `.env` со следующими переменными окружения:
```
# Django
SECRET_KEY=ключ_который_будет_использовать_django_для_хеширования
DJANGO_ALLOWED_HOSTS=ip_адрес_сервера, 127.0.0.1
DEBUG=False
EMAIL_HOST=адрес_хоста_почтового_сервиса
EMAIL_HOST_USER=email_адрес_для_работы_django_приложения
EMAIL_HOST_PASSWORD=пароль_от_этой_почты
EMAIL_PORT=порт_хоста_почтового_сервиса
EMAIL_USE_TLS=True

# Default User (лучше использовать username, как в YandexTracker)
ADMIN_USERNAME=имя_пользователя_который_будет_в_системе_по_умолчанию
ADMIN_EMAIL=email_пользователя_который_будет_в_системе_по_умолчанию
ADMIN_PASSWORD=пароль_пользователя_который_будет_в_системе_по_умолчанию

# Database (в режиме разработки можно оставить ip сервера)
# DB_HOST=ip_сервера
DB_HOST=dispatch_db
DB_PORT=5432
POSTGRES_DB=XXXX
POSTGRES_USER=XXXX
POSTGRES_PASSWORD=XXXX

# API TowerStore
TS_POLES_TL_URL=url_для_обновления_данных_по_опоре
TS_AVR_REPORT_URL=url_для_обновления_данных_по_подрядчику
TS_BS_REPORT_URL=url_для_обновления_данных_по_базовой_станции_и_операторам

# Default Contractors
DEFAULT_CONTRACTOR_EMAILS=список_пользователей_через_запятую_которым_будет_приходить_заявка_если_за_опорой_отсутсвует_подрядчик

# Email with incidents
PARSING_EMAIL_LOGIN=emai_адрес_почты_с_которой_собираются_заявки
PARSING_EMAIL_PSWD=пароль_адрес_почты_с_которой_собираются_заявки
PARSING_EMAIL_SERVER=адрес_хоста_почтового_сервиса
PARSING_EMAIL_PORT=порт_хоста_почтового_сервиса
# Папка по умолчанию для отправленных Email:
PARSING_EMAIL_SENT_FOLDER_NAME=&BB4EQgQ,BEAEMAQyBDsENQQ9BD0ESwQ1

# YandexTracker
YT_CLIENT_ID=client_id_полученный_ранее
YT_CLIENT_SECRET=client_secret_полученный_ранее
YT_ORGANIZATION_ID=id_организации_из_трекера
YT_ACCESS_TOKEN=токен_для_доступа_к_трекеру
YT_REFRESH_TOKEN=токен_для_востановления_основного_токена

# YandexTracker (настройка очереди и полей):
YT_QUEUE=имя_очереди_в_трекере

YT_DATABASE_ID_GLOBAL_FIELD_ID=ключ_глобального_поля_для_id_инцидента_в_системе
YT_EMAILS_IDS_GLOBAL_FIELD_ID=ключ_глобального_поля_для_id_сообщений_добавленных_к_инциденту_в_системе
YT_POLE_NUMBER_GLOBAL_FIELD_ID=ключ_глобального_поля_для_шифр_опоры
YT_BASE_STATION_GLOBAL_FIELD_ID=ключ_глобального_поля_для_номера_базовой_станции
YT_EMAIL_DATETIME_GLOBAL_FIELD_ID=ключ_глобального_поля_для_даты_первого_сообщения_по_инциденту
YT_IS_NEW_MSG_GLOBAL_FIELD_ID=ключ_глобального_поля_для_переключения_что_есть_новое_сообщение_по_инциденту
YT_SLA_DEADLINE_GLOBAL_FIELD_ID=ключ_глобального_поля_для_дедлайна_инцидента
YT_IS_SLA_EXPIRED_GLOBAL_FIELD_ID=ключ_глобального_поля_для_статуса_sla
YT_OPERATOR_NAME_GLOBAL_FIELD_NAME=ключ_глобального_поля_для_имени_оператора
YT_AVR_NAME_GLOBAL_FIELD_ID=ключ_глобального_поля_для_имени_подрядчика

YT_TYPE_OF_INCIDENT_LOCAL_FIELD_ID=ключ_локального_поля_для_выбора_типа_проблемы

# YandexTracker (кастомные статусы):
YT_ON_GENERATION_STATUS_KEY=ключ_статуса_на_генерации
YT_NOTIFY_OPERATOR_ISSUE_IN_WORK_STATUS_KEY=ключ_статуса_уведомляем_оператора
YT_NOTIFIED_OPERATOR_ISSUE_IN_WORK_STATUS_KEY=ключ_статуса_уведомили_оператора
YT_NOTIFY_OPERATOR_ISSUE_CLOSED_STATUS_KEY=ключ_статуса_уведомить_о_закрытии
YT_NOTIFIED_OPERATOR_ISSUE_CLOSED_STATUS_KEY=ключ_статуса_уведомили_о_закрытии
YT_NOTIFY_AVR_CONTRACTOR_IN_WORK_STATUS_KEY=ключ_статуса_передать_подрядчику
YT_NOTIFIED_AVR_CONTRACTOR_IN_WORK_STATUS_KEY=ключ_статуса_передано_подрядчику

# Telegram
TG_TOKEN=токен_telegram_для_уведомлений_работы_приложения
TG_DEFAULT_USER_ID=id_пользователя_telegram

```

### Установка Docker и Docker Compose (Ubuntu)
1. Обновите пакеты и установите зависимости:
```
sudo apt update && sudo apt install ca-certificates curl
```
2. Добавьте GPG-ключ и репозиторий Docker:
```
sudo install -m 0755 -d /etc/apt/keyrings
```
```
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo tee /etc/apt/keyrings/docker.asc > /dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
```
```
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```
3. Установите Docker:
```
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
4. Проверьте работу Docker:
```
sudo systemctl status docker 
```

Оркестр контейнеров настроен так, что лог файлы будут доступны на хост машине (mount), прямо в папке logs, но там еобходимо дать необходимые права на эту папку
sudo chmod -R 777 ./logs

аналогично с папкой data
sudo chmod -R 777 ./data

также .env примонтирован внутрь контейнера 
база данных также будет доступна по имени хоста

Данные базы данных и media файлы лежат в docker volume

2. Загрузите/обновите образы из Docker Hub:
```
sudo docker compose -f docker-compose.production.yml pull
```
4. Перезапустите сервисы:
```
sudo docker compose -f docker-compose.production.yml down
```
```
sudo docker compose -f docker-compose.production.yml up -d
```


### Настройка Nginx
1. Отредактируйте файл `/etc/nginx/sites-enabled/default` и добавьте туда минимально необходимую конфигурацию:
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
```
sudo nginx -t
```
```
sudo service nginx reload
```

### ✅ Готово!
Приложение будет доступно по адресу: `http://<хост_сервера>/`

sudo docker compose stop && sudo docker compose up --build -d

sudo docker compose exec dispatch_backend bash


sudo docker compose -f docker-compose.production.yml up





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
