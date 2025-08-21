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