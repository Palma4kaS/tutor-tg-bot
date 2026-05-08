# Деплой Mini App на VPS (Ubuntu/Debian)

## Шаг 1: Регистрация DuckDNS

1. Перейди на https://www.duckdns.org/
2. Войди через Google/GitHub/Twitter
3. Создай субдомен (например: `tutorapp`) → получишь `tutorapp.duckdns.org`
4. Скопируй свой **token** (он на главной странице после входа)
5. Укажи IP своего VPS сервера в поле и нажми "update ip"

## Шаг 2: Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем необходимые пакеты
sudo apt install -y nginx python3 python3-pip python3-venv certbot python3-certbot-nginx git

# Устанавливаем Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## Шаг 3: Копирование проекта на сервер

```bash
# Создаём папку для проекта
sudo mkdir -p /var/www/miniapp
sudo chown $USER:$USER /var/www/miniapp

# Копируем файлы (с локальной машины)
# Вариант 1: через scp
scp -r miniapp/* user@your-server-ip:/var/www/miniapp/

# Вариант 2: через git (если проект в репозитории)
cd /var/www/miniapp
git clone your-repo-url .
```

## Шаг 4: Настройка бэкенда

```bash
cd /var/www/miniapp/backend

# Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаём .env файл
cat > .env << 'EOF'
BOT_TOKEN=your_bot_token_here
TUTOR_FOLDER=tutor_123456789
CORS_ORIGINS=*
EOF

# Копируем базу данных (если она на другом сервере)
# scp user@old-server:/path/to/tutor_bot.db /var/www/miniapp/tutors/tutor_910518469/
```

## Шаг 5: Сборка фронтенда

```bash
cd /var/www/miniapp/frontend

# Устанавливаем зависимости
npm install

# Создаём .env для production
echo "VITE_API_URL=/api" > .env

# Собираем
npm run build
```

## Шаг 6: Создание systemd сервиса для бэкенда

```bash
sudo nano /etc/systemd/system/miniapp-api.service
```

Вставь:
```ini
[Unit]
Description=Tutor MiniApp API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/miniapp/backend
Environment="PATH=/var/www/miniapp/backend/venv/bin"
ExecStart=/var/www/miniapp/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Даём права
sudo chown -R www-data:www-data /var/www/miniapp

# Запускаем сервис
sudo systemctl daemon-reload
sudo systemctl enable miniapp-api
sudo systemctl start miniapp-api

# Проверяем статус
sudo systemctl status miniapp-api
```

## Шаг 7: Настройка nginx

```bash
sudo nano /etc/nginx/sites-available/miniapp
```

Вставь (замени `tutorapp.duckdns.org` на свой домен):
```nginx
server {
    listen 80;
    server_name tutorapptest.duckdns.org;

    # Фронтенд (статика)
    root /root/TelegramBot/RebornTgBot/miniapp/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # API бэкенда
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
# Активируем сайт
sudo ln -s /etc/nginx/sites-available/miniapp /etc/nginx/sites-enabled/

# Проверяем конфигурацию
sudo nginx -t

# Перезапускаем nginx
sudo systemctl restart nginx
```

## Шаг 8: Получение SSL сертификата (Let's Encrypt)

```bash
# Получаем сертификат (замени домен на свой)
sudo certbot --nginx -d tutorapp.duckdns.org

# Отвечай на вопросы:
# - Введи email
# - Согласись с условиями (Y)
# - Выбери редирект HTTP → HTTPS (2)
```

Certbot автоматически обновит конфиг nginx и добавит SSL.

## Шаг 9: Автообновление сертификата

```bash
# Проверяем автообновление
sudo certbot renew --dry-run

# Certbot уже добавил таймер, проверяем
sudo systemctl status certbot.timer
```

## Шаг 10: Регистрация Mini App в BotFather

1. Открой @BotFather в Telegram
2. Выбери своего бота
3. Нажми **Bot Settings** → **Menu Button** → **Configure Menu Button**
4. Введи URL: `https://tutorapp.duckdns.org`
5. Введи название кнопки: `Личный кабинет`

Или через команды:
```
/mybots → Выбери бота → Bot Settings → Menu Button → Configure menu button
URL: https://tutorapp.duckdns.org
Text: 📱 Личный кабинет
```

## Проверка

1. Открой `https://tutorapp.duckdns.org` в браузере — должен открыться Mini App
2. Открой `https://tutorapp.duckdns.org/api/docs` — должен открыться Swagger UI
3. Открой бота в Telegram и нажми кнопку меню — должен открыться Mini App

## Полезные команды

```bash
# Логи бэкенда
sudo journalctl -u miniapp-api -f

# Логи nginx
sudo tail -f /var/log/nginx/error.log

# Перезапуск бэкенда
sudo systemctl restart miniapp-api

# Перезапуск nginx
sudo systemctl restart nginx
```

## Обновление приложения

```bash
cd /var/www/miniapp

# Обновляем код
git pull

# Пересобираем фронтенд
cd frontend && npm install && npm run build

# Перезапускаем бэкенд
sudo systemctl restart miniapp-api
```
