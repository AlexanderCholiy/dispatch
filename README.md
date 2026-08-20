<h1 align="center">DISPATCH</h1>

**DISPATCH** — это полностью автономная платформа для управления инцидентами компании ООО «Новые Башни». Система автоматизирует процессы мониторинга, распределения задач и коммуникации с подрядчиками и заявителями, обеспечивая прозрачность и контроль сроков (SLA).
<div align="center">
  <img src=".github/images/dispatch/incidents_list/incidents_list.png" alt="Web интерфейс системы" width="95%">
  <br>
  <em>Рис. 1 — Web интерфейс системы</em>
</div>

---

## 📑 Оглавление
1. [Модель инцидента](#-модель-инцидента)
   - [Атрибуты инцидента](#атрибуты-инцидента)
   - [История и аудит](#история-и-аудит)
   - [Интеграция с электронной почтой](#интеграция-с-электронной-почтой)
   - [Инструменты коммуникации](#инструменты-коммуникации)
   - [Связи между инцидентами](#связи-между-инцидентами)
   - [Плановые работы](#плановые-работы)
2. [Как всё устроено под капотом](#-как-всё-устроено-под-капотом)
   - [Основные компоненты](#основные-компоненты)
   - [Управление процессами (Supervisor)](#управление-процессами-supervisor)
   - [Внутренний Nginx — обратный прокси и сервер статики](#внутренний-nginx--обратный-прокси-и-сервер-статики)
   - [Внешний Nginx — HTTPS](#внешний-nginx--https)
   - [Логирование и данные](#логирование-и-данные)
3. [Статистика и аналитика (Grafana)](#-статистика-и-аналитика-grafana)
   - [Сконфигурированные дашборды](#сконфигурированные-дашборды)
4. [Администрирование](#-администрирование)
   - [Роли пользователей](#роли-пользователей)
   - [Восстановление и безопасность](#восстановление-и-безопасность)
   - [Управление активным оборудованием](#управление-активным-оборудованием)

---

## 🗂 Модель инцидента
Инцидент — ключевой объект системы, привязанный к конкретной опоре и базовой станции (БС).
<div align="center">
  <img src=".github/images/dispatch/incident_detail/incident_form.png" alt="Карточка инцидента" width="95%">
  <br>
  <em>Рис. 2 — Основная форма карточки инцидента</em>
</div>

### Атрибуты инцидента
- **Классификация**: Тип и подтип инцидента.
- **Приоритет РВР**: Уровень срочности работ.
- **Категории работ**: Инцидент может включать несколько типов работ одновременно:
  - **АВР** (Аварийно-восстановительные работы) — SLA зависит от типа аварии.
  - **РВР** (Ремонтно-восстановительные работы) — SLA зависит от приоритета РВР.
  - **ДГУ** (Дизелирование) — фиксированный SLA 15 дней (превышение срока ведет к резкому росту затрат на топливо).
  - **ЭКС** (Эксплуатационные работы) — фиксированный SLA 15 дней.
- **Сроки**: Для каждой категории работ указываются даты начала и окончания.

### История и аудит
Система ведет полную историю изменений статусов и журнал модификации атрибутов (тип, подтип, привязка к опоре и т.д.).

### Интеграция с электронной почтой
Система автоматически обрабатывает входящие и исходящие письма компании, распределяя их по инцидентам.

**Алгоритм привязки писем к инцидентам**:
1. **По коду инцидента**: Поиск уникального кода в теме письма (приоритетный метод).
2. **По цепочке переписки**: Анализ заголовков Message-ID, Message-Reply-To, Message-Reference.
3. **По контенту**: Совпадение тела письма, отправителя и темы.

*Примечание: В редких случаях, если алгоритм находит несколько кандидатов, выбирается наиболее актуальный инцидент в цепочке.*

**Автоматизация процессов**:
- **Создание новых инцидентов**: Если входящее письмо не привязано к существующему инциденту, система автоматически создает новый. Ответственный диспетчер назначается автоматически с учетом его текущего графика работы и загрузки (балансировка нагрузки).
- **Распознавание объектов**: Если опора/БС не указана, система ищет шифр и номер БС в теме или теле письма.
- **Уведомления**:
  - Каждое новое входящее письмо ставит флаг «НЕ ПРОЧИТАНО» инциденту.
  - Формируются push-уведомления для ответственного лица и дежурных диспетчеров (в том числе вне графика, если требуется срочное вмешательство).
- **Обработка закрытых инцидентов**: При поступлении письма на закрытый инцидент система отправляет автоответ. При повторных обращениях (после N-го сообщения) инцидент автоматически открывается, и формируется уведомление об эскалации.
- **Архивация**: Скачиваются вложения и оригиналы писем (HTML-разметка сохраняется для удобного просмотра).
<div align="center">
  <div align="center">
    <img src=".github/images/dispatch/emails/email_detail.png" alt="Исходящее письмо по инциденту" width="95%">
    <br>
    <em>Рис. 3 — Карточка исходящего письма</em>
  </div>
  <br>
  <div align="center">
    <img src=".github/images/dispatch/incident_detail/incident_notification.png" alt="Уведомление по инциденту" width="95%">
    <br>
    <em>Рис. 4 — Уведомление по инциденту</em>
  </div>
  <br>
  <div align="center">
    <img src=".github/images/dispatch/notifications/notifications_list.png" alt="Список уведомлени" width="95%">
    <br>
    <em>Рис. 5 — Список уведомлений</em>
  </div>
</div>

### Инструменты коммуникации
- **Отправка писем**: Возможность писать новые письма или отвечать на существующие прямо из интерфейса системы.
- **Шаблоны**: Предусмотрены стандартные шаблоны (принятие работ, передача подрядчику по АВР/РВР, уведомление о закрытии). Все шаблоны редактируются перед отправкой.
- **Перенос писем**: Возможность переноса писем между инцидентами. Пользователи без прав администратора могут переносить только целые цепочки переписки.
- **Журнал событий**: Все действия (отправка, перенос, изменения) фиксируются в журнале с указанием автора и времени.
- **Комментарии**: Возможность обсуждения инцидента в режиме реального времени.
- **Отправка уведомлений в MAX**: Отправка критических уведомлений в мессенджер MAX при возникновении проблем высокого приоритета.
<div align="center">
  <div align="center">
    <img src=".github/images/dispatch/incident_detail/incident_emails.png" alt="Переписка по инциденту" width="95%">
    <br>
    <em>Рис. 6 — Переписка по инциденту</em>
  </div>
  <br>
  <div align="center">
    <img src=".github/images/dispatch/incident_detail/incident_comments.png" alt="Комментарии по инциденту" width="95%">
    <br>
    <em>Рис. 7 — Комментарии к инциденту</em>
  </div>
  <br>
  <div align="center">
    <img src=".github/images/dispatch/incident_detail/max_notification.png" alt="Уведомление в MAX" width="95%">
    <br>
    <em>Рис. 8 — Эскалация в MAX по инциденту</em>
  </div>
</div>

### Связи между инцидентами
Система позволяет связывать инциденты, задавая тип связи:
- **Связано с**: Общая информационная связь без ограничений.
- **Дубликат**: При закрытии основного инцидента система напомнит о необходимости закрыть дубликат.
- **Блокирует / Зависит от**: Запрет на закрытие инцидента, пока не закрыт связанный с ним (логика блокировки/зависимости).
<div align="center">
  <img src=".github/images/dispatch/incident_detail/incident_links.png" alt="Связанные инциденты" width="95%">
  <br>
  <em>Рис. 9 — Связанные инциденты</em>
</div>

> [!NOTE]
> Интеллектуальная подсказка: Система автоматически предлагает потенциально связанные инциденты с описанием причин (совпадение БС, тематика и пр.).

### Плановые работы
Отдельная сущность для управления плановыми мероприятиями (ПЛР).
- **Атрибуты**: Срок начала/окончания, привязка к опоре, автор, причина проведения.
- **Документация**: Привязка писем, по которым были согласованы работы.
- **Аудит**: Журнал событий изменений карточки ПЛР.
<div align="center">
  <img src=".github/images/dispatch/planned_works/planned_work_form.png" alt="Карточка плановой работы" width="95%">
  <br>
  <em>Рис. 10 — Карточка плановой работы</em>
</div>

---

## ⚙️ Как всё устроено под капотом
Система построена на **Django** с использованием микросервисной архитектуры. Все компоненты запускаются в изолированных Docker-контейнерах и общаются друг с другом через внутреннюю сеть.
```mermaid
graph TD
    User[Пользователь] --> ExternalNginx[Внешний Nginx<br>HTTPS]
    ExternalNginx --> Gateway[dispatch_gateway<br>Внутренний Nginx]
    
    Gateway --> Backend[dispatch_backend<br>Django]
    Gateway --> Grafana[dispatch_grafana<br>Мониторинг]
    
    Backend --> DB[dispatch_db<br>PostgreSQL]
    Backend --> Redis[dispatch_redis<br>Кэш]
    Backend --> RabbitMQ[dispatch_rabbitmq<br>Брокер задач]
    
    RabbitMQ --> Worker[dispatch_celery_worker<br>Фоновые задачи]
    RabbitMQ --> HeavyWorker[dispatch_celery_heavy_worker<br>Тяжелые задачи]
    RabbitMQ --> Beat[dispatch_celery_beat<br>Планировщик]
```

### Основные компоненты
Все сервисы описаны в файле `docker-compose.yml` и запускаются через Docker Compose. Каждый компонент работает в собственном контейнере, а взаимодействие между ними организовано через внутреннюю сеть `dispatch_network`.
| Сервис | Файл конфигурации | Назначение |
|--------|-------------------|------------|
| **`dispatch_db`** | `docker-compose.yml` | PostgreSQL — основное хранилище данных об инцидентах, пользователях и настройках |
| **`dispatch_redis`** | `docker-compose.yml` | Кэш-хранилище для сессий, временных данных и уведомлений |
| **`dispatch_rabbitmq`** | `docker-compose.yml` | Брокер сообщений для Celery (очереди задач: почта, уведомления) |
| **`dispatch_backend`** | `docker-compose.yml` + `Dockerfile` | Django-приложение — API, админка, WEB, бизнес-логика |
| **`dispatch_celery_worker`** | `docker-compose.yml` | Обработка обычных фоновых задач (отправка писем, уведомлений в MAX, автозакрытие) |
| **`dispatch_celery_heavy_worker`** | `docker-compose.yml` | Тяжелые фоновые задачи (формирование отчетов, выгрузка данных) |
| **`dispatch_celery_beat`** | `docker-compose.yml` | Планировщик периодических задач (cron-расписание) |
| **`dispatch_grafana`** | `docker-compose.yml` | Визуализация метрик и мониторинг системы (встраивается в интерфейс) |
| **`dispatch_gateway`** | `gateway/nginx.conf` | Nginx — единая точка входа, раздача статики, проксирование запросов |

> [!IMPORTANT]
> Все чувствительные настройки (пароли, ключи, секреты) вынесены в файл **`.env`**, который подключается к контейнерам через `env_file`. Это позволяет:
> - Не хранить секреты в коде
> - Использовать разные конфигурации для dev/prod
> - Безопасно передавать настройки между сервисами

> [!CAUTION]
> Автоперезапуск — `restart: unless-stopped` восстанавливает контейнеры после перезагрузки сервера или падения контейнера

### Управление процессами (Supervisor)
Бэкенд-платформа построена на базе **Python 3.12** и включает все необходимые системные зависимости (`PostgreSQL Client`, `ODBC Drivers`, `GDAL` и др.). 
Точкой входа служит скрипт `entrypoint.sh`. Он подготавливает окружение, после чего передает управление **Supervisor**. Этот инструмент изолированно запускает, контролирует и автоматически перезапускает ключевые сервисы внутри контейнера **dispatch_backend**:
| Процесс | Назначение | Режим работы |
| :--- | :--- | :--- |
| **django_init** | Применяет миграции БД и собирает статику | Однократно (при старте) |
| **django_seed** | Создает суперпользователя, системного бота и базовые настройки | Однократно (при старте) |
| **gunicorn** | Обслуживает WSGI/ASGI трафик Django (порт `8000`) | Постоянно |
| **cron** | Планировщик фоновых и периодических задач | Постоянно |
| **parsing_inbox_emails** | Парсинг входящей почты для авторегистрации инцидентов | Постоянно |
| **parsing_sent_emails** | Синхронизация исходящих писем с почтовым сервером | Постоянно |

> [!TIP]
> **Гибридный веб-сервер (Gunicorn + Uvicorn)**
> Использование связки `Gunicorn` (в качестве менеджера процессов) и воркеров `Uvicorn` позволяет эффективно обрабатывать как классические синхронные HTTP-запросы, так и асинхронные WebSocket-соединения. Конфигурация из 4 воркеров гарантирует параллельную обработку задач и устойчивость к нагрузкам.

### Внутренний Nginx — обратный прокси и сервер статики
Внутренний Nginx выполняет ключевые задачи:
  - **Обратный прокси**:	Перенаправляет запросы к Django
  - **Раздача статики**:	CSS, JS, изображения отдаются напрямую (быстрее)
  - **Rate Limiting**:	Защита от DDoS, брутфорса, балансирует нагрузку
  - **WebSocket**:	Поддержка реального времени
  - **GZIP** сжатие	Ускоряет загрузку страниц
Безопасная раздача медиа:
  - **Публичные файлы (/media/public/)**: доступны напрямую через Nginx
  - **Приватные файлы (/media/)** — только через Django с проверкой прав
> **Принцип**: Django проверяет права и отдаёт Nginx команду X-Accel-Redirect. Nginx сам отдаёт файл, не нагружая Python.

> [!TIP]
> **Автоматический сброс кэша**
> При каждой сборке проекта Django генерирует уникальные хеши в именах файлов статики (CSS, JS). Это позволяет кэшировать файлы в браузерах пользователей навсегда для максимальной скорости загрузки, а при обновлении кода изменения применятся мгновенно и без ручной очистки кэша.

### Внешний Nginx — HTTPS
Для защиты трафика используется внешний Nginx, который:
  - Принимает HTTP/HTTPS-запросы от пользователей
  - Шифрует трафик (TLSv1.2 / TLSv1.3)
  - Перенаправляет HTTP → HTTPS
  - Проксирует запросы к внутреннему Nginx

Пример конфигурации `/etc/nginx/sites-enabled/default`:
```nginx
server_tokens off;

server {
        listen 80;
        server_name <SERVER_IP> <DOMAIN_NAME>;

        return 301 https://$host$request_uri;
}

server {
        listen 443 ssl;

        server_name <SERVER_IP> <DOMAIN_NAME>;

        ssl_certificate /etc/ssl/certs/newtowers.ru.crt;
        ssl_certificate_key /etc/ssl/private/newtowers.ru.key;

        # Безопасные протоколы и шифры:
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Защита от downgrade-атак:
        ssl_prefer_server_ciphers on;

        client_max_body_size 105M;

        location / {
                proxy_set_header Host $http_host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;

                proxy_pass http://<SERVER_IP>:8000;
 
        }

        location /ws/ {
                proxy_pass http://<SERVER_IP>:8000;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                proxy_set_header Host $host;

                proxy_read_timeout 3600s;
                proxy_send_timeout 3600s;

    }
}
```
| Nginx | Роль | Маршрут |
| :--- | :--- | :--- |
| **Внешний (Хост)** | HTTPS-терминация, шифрование (порт 443) | проксирует на `localhost:8000` |
| **Внутренний (Контейнер)** | Раздача статики/медиа, маршрутизация | принимает на порт `80` внутри Docker сети |

### Логирование и данные
Для обеспечения отказоустойчивости, удобного мониторинга и сохранения состояния системы все критически важные файлы вынесены за пределы изолированных контейнеров на хост-машину.

#### Журналирование событий (`./logs/`)
Вся история работы системы аккумулируется в единой локальной директории, разделенной по сервисам:
* `django/` и `celery/` — логи бизнес-логики и фоновых задач.
* `nginx/` — логи запросов (access) и ошибок (error) веб-серверов.
* `supervisor/` — состояние и вывод системных процессов бэкенда.
* `grafana/` — метрики работы панелей мониторинга.

> [!IMPORTANT]
> **Защита дискового пространства**
> Для всех типов логов настроена автоматическая ротация. По достижении лимита старые записи архивируются и удаляются, предотвращая переполнение диска сервера.

#### Работа с данными (`./data/`)
Директория предназначена для хранения изменяемых изолированных данных приложения:
  - **Выгрузки и отчеты** — файлы экспорта/импорта, тяжелые аналитические отчеты и документы.
  - **Резервные копии** — дампы базы данных (БД).
  - **Конфиденциальные данные** — API-ключи ботов, токены.

> [!NOTE]
> Локальные папки `./logs/` и `./data/` монтируются в Docker-контейнеры через `volumes`. Это позволяет разработчикам и администраторам анализировать логи и работать с файлами напрямую из корня проекта на хосте, без необходимости входить внутрь контейнеров через `docker exec`.

---

## 📊 Статистика и аналитика (Grafana)
Для визуализации метрик и построения интерактивных дашбордов используется **Grafana**. Это решение позволило полностью отказаться от разработки кастомных JavaScript-виджетов и фронтенд-кода для аналитики.

**Ключевые преимущества подхода:**
  - **Скорость** — дашборды собираются в No-Code интерфейсе за несколько минут.
  - **Гибкость** — добавление новых графиков и метрик не требует изменения кода приложения.
  - **Эффективность** — визуализация (графики, таблицы, тепловые карты, gauge) формируется напрямую через SQL-запросы к БД.

<div align="center">
  <img src=".github/images/grafana/grafana_map.png" alt="Интерфейс Grafana" width="95%">
  <br>
  <em>Рис. 11 — Настройка карты в интерфейсе Grafana</em>
</div>

> [!NOTE]
> Панель Grafana интегрирована в интерфейс приложения и доступна по внутреннему роуту: `/grafana`.

> [!CAUTION]
> **Минимизация привилегий (Принцип наименьших прав)**
> Для интеграции с Grafana используется выделенная учетная запись СУБД в режиме **Read-Only (только чтение)**. Это полностью исключает риск случайного изменения или удаления данных и локализует угрозу в случае компрометации аналитической панели.

### Сконфигурированные дашборды

| Дашборд | Файл конфигурации | Назначение |
| :--- | :--- | :--- |
| **Карта инцидентов** | `grafana-dashboard-map.json` | Геораспределение инцидентов на карте. |
| **Статистика по инцидентам** | `grafana-dashboard-statistic.json` | Агрегированные метрики, тренды, графики и таблицы. |

<div align="center">
  <img src=".github/images/grafana/app_statistic.png" alt="Встроенная статистика по инцидентам" width="95%">
  <br>
  <em>Рис. 12 — Статистика по инцидентам</em>
</div>

> [!IMPORTANT]
> Дашборды встраиваются в интерфейс приложения через `iframe`. Для их корректной идентификации в коде используются следующие UID-константы:
> - `GENERAL_DISPATCH_STATISTICS_UID` — уникальный идентификатор дашборда статистики.
> - `GENERAL_DISPATCH_MAP_UID` — уникальный идентификатор дашборда карты.

---

## 🛠 Администрирование
Для управления системой используется встроенная админ-панель **Django**. Доступ к ней имеют только пользователи с правами суперпользователя или персонала.

Через встроенную панель администратора можно гибко настраивать правила SLA, управлять пользователями и контролировать статус их активации.

> [!NOTE]
> Доступ к конкретным таблицам и функциям можно гибко настраивать через права доступа.

### Роли пользователей
В системе предусмотрены следующие роли:
| Роль | Доступ и возможности |
| :--- | :--- |
| **ГОСТЬ** | Минимальный доступ — только вход в систему. Автоматически назначается новым пользователям сразу после подтверждения электронной почты. |
| **ПОЛЬЗОВАТЕЛЬ** | Базовые права: просмотр инцидентов и добавление комментариев. Права на редактирование данных отсутствуют. |
| **ДИСПЕТЧЕР** | Полный административный доступ к управлению инцидентами. Доступно автоматическое распределение заявок на основе рабочего расписания. |
| **СТАЖЕР** | Обладает правами диспетчера со следующими жесткими ограничениями:<br>- Не может создавать новые инциденты<br>- Не может редактировать чужие инциденты<br>- Не может переносить письма<br>- Для тренировок и обучения выделена тестовая опора `undefined` |
| **ПОДРЯДЧИК** | Изолированный доступ. Видит и обрабатывает инциденты исключительно в зоне ответственности своей организации (привязка к подрядной организации обязательна). |
| **ЭНЕРГЕТИК** | Доступ в режиме чтения: просмотр аналитических данных и выгрузка отчетов из внешней базы данных энергетических компаний. |
| **Диспетчер со статусом персонала** | Расширенная роль диспетчера: может вручную отключать автоматическое назначение заявок настроив расписание, при этом продолжает гарантированно получать уведомления при эскалации инцидентов. |

### Восстановление и безопасность
  - **Восстановление пароля** — через email
  - **Смена email** — если новый адрес не занят
  - **Подтверждение почты** — обязательное условие для активации учетной записи

### Управление активным оборудованием
В админ-панели доступна таблица с активным оборудованием. Если оборудование на опоре или сама опора присылает ошибку из системы мониторинга — в диспетчерской автоматически создается **эскалация инцидента**.

---


---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---
---












































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
1. Запустите необходимые контейнеры через Docker Compose: базу данных PostgreSQL, Redis, брокер сообщений RabbitMQ, воркеры Celery для фоновой обработки задач и Grafana для дашбордов:
```bash
sudo docker compose up -d --build --force-recreate dispatch_db dispatch_redis dispatch_rabbitmq dispatch_grafana dispatch_celery_heavy_worker dispatch_celery_worker dispatch_celery_beat
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
