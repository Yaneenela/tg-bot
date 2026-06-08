#!/bin/bash
set -e

# ===== Деплой VPN бота на VPS =====
# Запускать от root или пользователя с sudo

BOT_DIR="/opt/vpnbot"
REPO_DIR="$BOT_DIR/repo"
ENV_FILE="$BOT_DIR/.env"
SERVICE_FILE="/etc/systemd/system/vpnbot.service"

echo "=== 1. Устанавливаем зависимости ==="
apt update
apt install -y python3 python3-pip python3-venv git curl

echo "=== 2. Создаём пользователя для бота ==="
id -u vpnbot &>/dev/null || useradd -m -s /bin/bash -d "$BOT_DIR" vpnbot

echo "=== 3. Копируем проект ==="
mkdir -p "$BOT_DIR"
# Если проект уже склонирован — просто обновить
if [ -d "$REPO_DIR/.git" ]; then
    cd "$REPO_DIR" && git pull
else
    # Замените URL на ваш репозиторий
    # git clone https://github.com/you/vpnbot.git "$REPO_DIR"
    echo "!!! Скопируйте файлы в $REPO_DIR вручную !!!"
    echo "    Или выполните: git clone <ваш-репозиторий> $REPO_DIR"
    exit 1
fi

echo "=== 4. Создаём .env ==="
if [ ! -f "$ENV_FILE" ]; then
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    echo "!!! Заполните $ENV_FILE своими данными !!!"
    echo "    nano $ENV_FILE"
fi

echo "=== 5. Виртуальное окружение + зависимости ==="
python3 -m venv "$BOT_DIR/venv"
source "$BOT_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$REPO_DIR/requirements.txt"

echo "=== 6. Создаём systemd-сервис ==="
cat > "$SERVICE_FILE" << 'SERVICEEOF'
[Unit]
Description=VPN Bot (aiogram + FastAPI)
After=network.target

[Service]
Type=simple
User=vpnbot
Group=vpnbot
WorkingDirectory=/opt/vpnbot/repo
EnvironmentFile=/opt/vpnbot/.env
ExecStart=/opt/vpnbot/venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "=== 7. Права доступа ==="
chown -R vpnbot:vpnbot "$BOT_DIR"
chmod 600 "$ENV_FILE"
chmod 644 "$SERVICE_FILE"

echo "=== 8. Запускаем ==="
systemctl daemon-reload
systemctl enable vpnbot
systemctl start vpnbot

echo ""
echo "=== ГОТОВО ==="
echo "Проверить статус: systemctl status vpnbot"
echo "Посмотреть логи: journalctl -u vpnbot -f"
echo "Редактировать .env: nano $ENV_FILE"
echo "Перезапустить: systemctl restart vpnbot"
