# Инструкция по установке на VPS

## 1. Подготовка

Что нужно иметь:
- VPS с Ubuntu 22.04+ / Debian 11+
- Установленный 3x-ui панель
- Домен (для HTTPS подписки)
- Доступ по SSH (root)

## 2. Настройка 3x-ui

Зайди в веб-интерфейс панели:

**A. Subscription Server**
- Настройки → Subscription → включить
- Порт: `10882`
- Путь: `/sub/`
- Если есть домен — укажи его в `Sub Domain`

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
| `XUI_URL` | `https://127.0.0.1:2053` (или твой IP) |
| `XUI_TOKEN` | Токен из 3x-ui (Settings → Security → API Token) |
| `XUI_INSECURE=true` | Оставить `true`, если самоподписной сертификат |
| `YOOKASSA_SHOP_ID` | Из личного кабинета ЮKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ ЮKassa |
| `YOOKASSA_RETURN_URL` | `https://t.me/твой_бот` |
| `SUB_URL` | `https://sub.твой-домен:10882/sub/` |
| `WEBHOOK_HOST` | `https://sub.твой-домен` |
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

## 7. Настройка nginx + HTTPS (для подписки)

Если есть домен `sub.твой-домен`, направь его на IP сервера (A-запись).

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Создай `/etc/nginx/sites-available/sub`:

```nginx
server {
    listen 80;
    server_name sub.твой-домен;

    location /sub/ {
        proxy_pass http://127.0.0.1:10882;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Включить сайт
ln -sf /etc/nginx/sites-available/sub /etc/nginx/sites-enabled/

# Получить SSL
certbot --nginx -d sub.твой-домен --non-interactive --agree-tos -m admin@твой-домен

# Перезапустить nginx
systemctl restart nginx
```

Теперь ссылка на подписку будет:
```
https://sub.твой-домен/sub/SUBID
```

## 8. Настройка вебхука ЮKassa

FastAPI слушает на `127.0.0.1:8000` — он не доступен снаружи.
ЮKassa должен слать уведомления на внешний URL.

**Вариант A — через nginx (рекомендую):**

Добавь в тот же `/etc/nginx/sites-available/sub`:

```nginx
location /webhook/ {
    proxy_pass http://127.0.0.1:8000;
}
```

Потом:
```bash
systemctl reload nginx
```

В кабинете ЮKassa → Настройки → HTTP-уведомления:
- URL: `https://sub.твой-домен/webhook/yookassa`
- События: `payment.succeeded`

**Вариант B — открыть порт 8000 (проще, но менее безопасно):**

В `.env` поменяй `WEBHOOK_HOST` на IP сервера.
В фаерволле открой порт 8000.

В кабинете ЮKassa:
- URL: `http://IP-сервера:8000/webhook/yookassa`

## 9. Полезные команды

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

## 10. Структура .env (для проверки)

```
BOT_TOKEN=7234567890:AAH...
XUI_URL=https://127.0.0.1:2053
XUI_TOKEN=твой-токен-из-3x-ui
XUI_INSECURE=true
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=test_...
YOOKASSA_RETURN_URL=https://t.me/твой_бот
SUB_URL=https://sub.твой-домен/sub/
SUB_DOMAIN=sub.твой-домен
WEBHOOK_HOST=https://sub.твой-домен
WEBHOOK_PORT=8000
DATABASE_URL=sqlite+aiosqlite:///bot/db.sqlite3
PRICE_30D=100
PRICE_60D=200
PRICE_90D=300
EXTRA_DEVICE_PRICE=30
MAX_DEVICES=10
BASE_DEVICES=3
ADMIN_IDS=[твой_telegram_id]
```
