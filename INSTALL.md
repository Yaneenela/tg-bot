# Инструкция по установке на VPS

## 1. Подготовка

Что нужно иметь:
- VPS с Ubuntu 22.04+ / Debian 11+
- Установленный 3x-ui панель
- Доступ по SSH (root)

## 2. Настройка 3x-ui

Зайди в веб-интерфейс панели:

**A. Subscription Server** (если ещё не включён)
- Настройки → Subscription → включить
- Порт: твой (по умолч. 10882)
- Путь: `/sub/`

**B. API Token**
- Настройки → Security → API Token
- Создать токен
- **Скопировать токен сразу** — он показывается один раз

**C. Inbound**
- Вкладка `Inbounds`
- Создать или выбрать существующий Inbound
- Запомнить его ID (номер в таблице)

## 3. Установка бота на VPS

```bash
# Зайти на сервер
ssh root@твой-сервер

# Установить зависимости
apt update && apt install -y git python3 python3-pip python3-venv

# Скачать бота
git clone https://github.com/Yaneenela/tg-bot.git /opt/vpnbot
cd /opt/vpnbot

# Создать виртуальное окружение и установить пакеты
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Настройка .env

```bash
cp .env.example .env
nano .env
```

Заполни поля:

| Поле | Что писать |
|------|-----------|
| `BOT_TOKEN` | Токен от @BotFather (получить: `/newbot`) |
| `XUI_URL` | `https://127.0.0.1:2053` (или твой IP/домен) |
| `XUI_TOKEN` | Токен из 3x-ui (Settings → Security → API Token) |
| `XUI_INSECURE=true` | Оставить `true`, если самоподписной сертификат |
| `XUI_BASE_PATH` | Web Base Path из 3x-ui Settings → General (по умолч. `/panel`) |
| `YOOKASSA_SHOP_ID` | Из личного кабинета ЮKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ ЮKassa |
| `YOOKASSA_RETURN_URL` | `https://t.me/твой_бот` |
| `SUB_URL` | Твоя существующая ссылка на подписку (до `/sub/`) |
| `SUB_DOMAIN` | Необязательно, можно оставить пустым |
| `ADMIN_IDS` | Твой telegram ID (узнать у @userinfobot) |

Остальное можно не трогать.

## 5. Запуск (проверка)

```bash
source venv/bin/activate
python -m bot.main
```

Если всё ок — бот запустился, в консоли будут логи.
Напиши `/start` в Telegram боте → должно ответить.

**Остановить:** `Ctrl+C`

## 6. Автозапуск (systemd)

```bash
cat > /etc/systemd/system/vpnbot.service << 'EOF'
[Unit]
Description=VPN Bot
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/vpnbot
EnvironmentFile=/opt/vpnbot/.env
ExecStart=/opt/vpnbot/venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vpnbot
systemctl start vpnbot

# Проверить
systemctl status vpnbot

# Логи
journalctl -u vpnbot -f
```

## 7. Как работает оплата (без вебхуков)

Бот **не требует** открытых портов или nginx для приёма платежей.

Схема:
1. Пользователь нажимает «Оплатить» → бот создаёт платёж в ЮKassa → выдаёт ссылку
2. Пользователь переходит по ссылке, оплачивает на сайте ЮKassa
3. Бот **каждые 30 секунд** проверяет статус неоплаченных платежей через API ЮKassa
4. Как только статус `succeeded` — бот активирует подписку и присылает ссылку

Никаких вебхуков, открытых портов, nginx, доменов для бота не нужно.

## 8. Полезные команды

```bash
# Перезапуск бота
systemctl restart vpnbot

# Логи в реальном времени
journalctl -u vpnbot -f

# Обновление бота (когда пушим новые версии)
cd /opt/vpnbot
git pull
systemctl restart vpnbot

# Проверить что бот запущен
systemctl status vpnbot

# Остановить бота
systemctl stop vpnbot
```

## 9. Структура .env (для проверки)

```
BOT_TOKEN=7234567890:AAH...
XUI_URL=https://127.0.0.1:2053
XUI_TOKEN=твой-токен-из-3x-ui
XUI_INSECURE=true
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=test_...
YOOKASSA_RETURN_URL=https://t.me/твой_бот
SUB_URL=https://твой-домен:2096/sub/
SUB_DOMAIN=твой-домен
DATABASE_URL=sqlite+aiosqlite:///bot/db.sqlite3
PRICE_30D=100
PRICE_60D=200
PRICE_90D=300
EXTRA_DEVICE_PRICE=30
MAX_DEVICES=10
BASE_DEVICES=3
ADMIN_IDS=[твой_telegram_id]
```
