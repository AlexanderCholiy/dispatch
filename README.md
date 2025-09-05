# dispatch
Сервер диспетчеризации, завязанный на YandexTracker


Установка Docker
# Обновляем пакеты
sudo apt update && sudo apt upgrade -y

# Ставим зависимости
sudo apt install -y ca-certificates curl gnupg lsb-release

# Добавляем официальный GPG-ключ Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Добавляем репозиторий Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Устанавливаем Docker и docker-compose
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

Проверка установки
sudo systemctl enable docker
sudo systemctl start docker
docker --version

# Запуск PostgreSQL
sudo docker compose up -d

# Запуск managment команд в фоне
nohup python manage.py my_command > my_command.log 2>&1 &


# Для работы Яндекс трекера необходимо добавить соответсвующие поля и в рабочий процесс
очереди добавить Инцидент (ключ incident)


# Команды, объединённые символами &&, выполняются последовательно;
# вторая команда выполнится, только если первая выполнилась успешно.
# Ключ --build для docker compose up означает,
# что перед запуском нужно пересобрать образы
sudo docker compose stop && sudo docker compose up --build 

<!-- sudo docker container ls -a -->


# ==================================================
# CRON JOBS CONFIGURATION
# ==================================================
# m h dom mon dow user  command
# | |  |   |   |   |    |
# | |  |   |   |   |    +--- команда для выполнения
# | |  |   |   |   +-------- пользователь (опционально)
# | |  |   |   +------------ день недели (0-7, 0=7=воскресенье)
# | |  |   +---------------- месяц (1-12)
# | |  +-------------------- день месяца (1-31)
# | +----------------------- час (0-23)
# +------------------------- минута (0-59)

Ошибка говорит о том, что ваш crontab файл не заканчивается пустой строкой — cron требует, чтобы последняя строка была завершающей новой строкой.

# Удаление неизвестных файлов - каждый день в 00:00:
0 0 * * * root cd /app && python manage.py delete_unknown_files >> /app/logs/cron.log 2>&1

# Обновление данных из TimescaleDB - каждый день в 20:00:
0 20 * * * root cd /app && python manage.py update_data_from_ts >> /app/logs/cron.log 2>&1

# ==================================================
# ПОЛЕЗНЫЕ ПРИМЕРЫ:
# ==================================================
# * * * * *    - каждую минуту
# 0 * * * *    - каждый час в начале часа
# 0 12 * * *   - каждый день в 12:00
# 0 0 * * 0    - каждое воскресенье в 00:00
# 0 0 1 * *    - первого числа каждого месяца
# */5 * * * *  - каждые 5 минут


Перейдите в директорию, где лежит файл docker-compose.yml, и выполните миграции:
Открыть терминал dispatch_backend
sudo docker compose exec dispatch_backend bash


sudo docker compose -f docker-compose.production.yml up







mkdir -p ./logs/supervisor
chmod -R 777 ./logs


rm -rf ~/.vscode-server
chmod -R 777 /home/a.choliy/dispatch/logs