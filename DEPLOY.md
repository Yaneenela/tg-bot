# Деплой бота на VPS

## Способ 1: Через git (рекомендую)

У тебя уже есть папка `proekt2` — залей её в Git-репозиторий (GitHub/GitLab), а на VPS просто склонируй.

### Шаг 1: Залить проект на GitHub (или GitLab)

```bash
# У тебя на ПК (уже в папке proekt2):
git remote add origin https://github.com/твой-ник/vpnbot.git
git add .
git commit -m "initial"
git push -u origin main
```

### Шаг 2: Зайти на VPS по SSH

```bash
ssh root@твой-сервер
```

### Шаг 3: Установить всё одной командой

```bash
export REPO_URL="https://github.com/твой-ник/vpnbot.git"
export BOT_DIR="/opt/vpnbot"

apt update && apt install -y git python3 python3-pip python3-venv
git clone "$REPO_URL" "$BOT_DIR"

cd "$BOT_DIR"
cp .env.example .env
nano .env   # <-- ЗАПОЛНИТЬ ВСЕ ПОЛЯ!
```

### Шаг 4: Заполнить .env

| Поле | Что вписать |
|------|------------|
| `BOT_TOKEN` | Токен от @BotFather |
| `XUI_URL` | Адрес панели 3x-ui (https://127.0.0.1:2053) |
| `XUI_TOKEN` | Settings → Security → API Token → создать |
| `YOOKASSA_SHOP_ID` | Из личного кабинета ЮKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ из ЮKassa |
| `SUB_URL` | `https://твой-домен:10882/sub/` |
| `WEBHOOK_HOST` | `https://твой-домен` (для вебхуков ЮKassa) |
| `ADMIN_IDS` | Твой telegram_id (узнать у @userinfobot) |

### Шаг 5: Запустить

```bash
# Создать venv и установить зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запустить
python -m bot.main
```

### Шаг 6: Настроить автозапуск (systemd)

```bash
cat > /etc/systemd/system/vpnbot.service << 'EOF'
[Unit]
Description=VPN Bot
After=network.target

[Service]
Type=simple
User=root
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
systemctl status vpnbot
```

### Шаг 7: Настроить nginx для подписки (чтобы HTTPS)

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Файл `/etc/nginx/sites-available/sub.твой-домен`:
```nginx
server {
    listen 443 ssl;
    server_name sub.твой-домен;

    ssl_certificate /etc/letsencrypt/live/sub.твой-домен/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sub.твой-домен/privkey.pem;

    location /sub/ {
        proxy_pass http://127.0.0.1:10882;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name sub.твой-домен;
    return 301 https://$server_name$request_uri;
}
```

```bash
ln -s /etc/nginx/sites-available/sub.твой-домен /etc/nginx/sites-enabled/
certbot --nginx -d sub.твой-домен
systemctl restart nginx
```

### После этого:
- **Бот работает**: `systemctl status vpnbot`
- **Логи**: `journalctl -u vpnbot -f`
- **Перезапуск**: `systemctl restart vpnbot`
- **Ссылка на подписку**: `https://sub.твой-домен/sub/SUBID`

## Шаг 8: Настроить вебхук ЮKassa

В кабинете ЮKassa → Настройки → HTTP-уведомления:
- URL: `https://твой-домен:8000/webhook/yookassa`
- События: `payment.succeeded`

> **Важно**: порт 8000 не должен быть открыт наружу!  
> ЮKassa умеет ходить на любой порт, либо поставь nginx прокси.

---

## Способ 2: Вручную через SCP (если нет git)

На своём ПК:
```bash
# Упаковать проект
tar -czf vpnbot.tar.gz bot/ requirements.txt .env.example

# Закинуть на сервер
scp vpnbot.tar.gz root@твой-сервер:/opt/

# На сервере:
ssh root@твой-сервер
cd /opt
tar -xzf vpnbot.tar.gz -C vpnbot
# дальше всё то же самое (шаги 4-8)
```
