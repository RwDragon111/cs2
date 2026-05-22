# CS2 DMarket -> CSGO Market Arbitrage Bot

Telegram-бот для анализа арбитража CS2-скинов: бот ищет предметы, которые можно купить на DMarket и потенциально продать в существующий buy order на CSGO Market с прибылью после комиссий.

По умолчанию включен безопасный `DEMO` режим. Реальные покупки/продажи не выполняются автоматически.

## 1. Локальный запуск на компьютере

### 1.1. Установи Python

Нужен Python `3.11+`.

Проверка:

```bash
python --version
```

На Windows иногда команда называется:

```powershell
py --version
```

### 1.2. Создай виртуальное окружение

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.3. Создай `.env`

Windows PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
```

Linux / macOS:

```bash
cp .env.example .env
nano .env
```

Минимально заполни:

```env
TELEGRAM_BOT_TOKEN=токен_бота_от_BotFather
AUTHORIZED_TELEGRAM_ID=твой_telegram_id
DEFAULT_TRADING_MODE=DEMO
ALLOW_REAL_TRADING=false
```

Для первого теста без реальных API включи mock-рынки:

```env
USE_MOCK_MARKETS=true
SCAN_INTERVAL_SECONDS=60
```

Так бот будет создавать тестовые сделки без подключения к DMarket и CSGO Market.

### 1.4. Запусти бота локально

Windows PowerShell:

```powershell
python -m app.main
```

Linux / macOS:

```bash
python -m app.main
```

После запуска открой Telegram и напиши боту:

```text
/start
/status
/deals
/balance
/demo_stats
```

Если включен `USE_MOCK_MARKETS=true`, команда `/deals` должна показать тестовую сделку.

### 1.5. Остановить локально

В терминале нажми:

```text
Ctrl+C
```

## 2. Запуск на VPS через screen

Этот вариант удобен для простого запуска на удаленном сервере: бот продолжит работать после выхода из SSH.

Ниже пример для Ubuntu/Debian VPS.

### 2.1. Подключись к серверу

```bash
ssh root@SERVER_IP
```

или под обычным пользователем:

```bash
ssh username@SERVER_IP
```

### 2.2. Установи зависимости сервера

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git screen
```

Проверка:

```bash
python3 --version
screen --version
```

### 2.3. Загрузи проект на сервер

Если проект лежит в GitHub:

```bash
cd /opt
sudo git clone REPO_URL cs2-arbitrage-bot
sudo chown -R $USER:$USER /opt/cs2-arbitrage-bot
cd /opt/cs2-arbitrage-bot
```

Если ты загружаешь папку вручную через SFTP, положи ее, например, сюда:

```bash
/opt/cs2-arbitrage-bot
```

и зайди в нее:

```bash
cd /opt/cs2-arbitrage-bot
```

### 2.4. Создай venv и установи зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.5. Настрой `.env`

```bash
cp .env.example .env
nano .env
```

Минимальные настройки:

```env
TELEGRAM_BOT_TOKEN=токен_бота_от_BotFather
AUTHORIZED_TELEGRAM_ID=твой_telegram_id
DEFAULT_TRADING_MODE=DEMO
ALLOW_REAL_TRADING=false
USE_MOCK_MARKETS=false
```

Для первого безопасного теста на VPS можно временно поставить:

```env
USE_MOCK_MARKETS=true
SCAN_INTERVAL_SECONDS=60
```

Когда проверишь Telegram-бота, верни:

```env
USE_MOCK_MARKETS=false
```

и добавь API-ключи:

```env
DMARKET_API_KEY=
DMARKET_API_SECRET=
CSGO_MARKET_API_KEY=
```

### 2.6. Запусти бота в screen

Создай screen-сессию:

```bash
screen -S cs2bot
```

Внутри screen запусти:

```bash
cd /opt/cs2-arbitrage-bot
source .venv/bin/activate
python -m app.main
```

Чтобы выйти из screen и оставить бота работать:

```text
Ctrl+A
D
```

То есть сначала нажми `Ctrl+A`, отпусти, потом нажми `D`.

### 2.7. Вернуться к работающему боту

Посмотреть screen-сессии:

```bash
screen -ls
```

Вернуться:

```bash
screen -r cs2bot
```

### 2.8. Остановить бота в screen

Зайди обратно:

```bash
screen -r cs2bot
```

Останови процесс:

```text
Ctrl+C
```

Выйди из screen:

```bash
exit
```

Если нужно принудительно закрыть screen-сессию:

```bash
screen -S cs2bot -X quit
```

### 2.9. Логи

Основной лог пишется сюда:

```bash
tail -f logs/app.log
```

Если бот запущен прямо в screen, текущий вывод также виден при:

```bash
screen -r cs2bot
```

## 3. Запуск на VPS через Docker

Альтернатива `screen`, если хочешь запускать контейнером:

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

Данные SQLite и логи сохраняются в:

```text
data/
logs/
```

## 4. Запуск через systemd

Для постоянного production-запуска лучше `systemd`, потому что сервис сам поднимется после перезагрузки VPS.

Файл:

```bash
sudo nano /etc/systemd/system/cs2-arbitrage-bot.service
```

Содержимое:

```ini
[Unit]
Description=CS2 Arbitrage Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/cs2-arbitrage-bot
EnvironmentFile=/opt/cs2-arbitrage-bot/.env
ExecStart=/opt/cs2-arbitrage-bot/.venv/bin/python -m app.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cs2-arbitrage-bot
sudo systemctl start cs2-arbitrage-bot
sudo systemctl status cs2-arbitrage-bot
```

Логи:

```bash
sudo journalctl -u cs2-arbitrage-bot -f
```

## 5. Telegram-команды

- `/start` - запуск и главное меню.
- `/status` - статус сканера, последнее сканирование, ошибки, uptime.
- `/balance` - баланс в текущем режиме.
- `/deals` - найденные сделки.
- `/best` - лучшие сделки по ROI и прибыли.
- `/inventory` - купленные скины и текущие сделки.
- `/locked` - предметы в trade lock.
- `/ready` - предметы, готовые к продаже.
- `/settings` - текущие фильтры и комиссии.
- `/watch <название или URL>` - добавить предмет в точный DMarket-поиск. Можно вставить ссылку DMarket или CSGO Market.
- `/watchlist` - показать предметы, которые всегда проверяются точечным поиском.
- `/scan_item <название или URL>` - сразу проверить конкретный предмет без ожидания общего сканирования.
- В карточке сделки есть кнопки `DMarket` и `CSGO Market` для быстрого открытия предмета на обеих площадках.
- Кнопки `Скрыть сделку`, `Отметить как куплено` и `Отметить как продано` удаляют исходную карточку из чата после успешного действия.
- `/pause` - поставить сканер на паузу.
- `/resume` - возобновить сканирование.
- `/mode` - текущий режим `DEMO` или `REAL`.
- `/demo_on` - включить DEMO.
- `/demo_off` - включить REAL, если разрешено в `.env`.
- `/demo_balance` - демо-баланс.
- `/demo_set_balance 100000` - установить демо-баланс.
- `/demo_reset` - сбросить демо-счет.
- `/demo_stats` - статистика демо-торговли.
- `/help` - справка.

## 6. Важные настройки `.env`

```env
SCAN_INTERVAL_SECONDS=300
MIN_PROFIT_PERCENT=5
MIN_PROFIT_ABSOLUTE=100
MIN_ITEM_PRICE=300
MAX_ITEM_PRICE=50000
MIN_LIQUIDITY_SCORE=60
MAX_PRICE_SPIKE_PERCENT=25
PRICE_HISTORY_DAYS=30
DMARKET_FEE_PERCENT=0
CSGO_MARKET_FEE_PERCENT=5
WITHDRAWAL_FEE_PERCENT=0
TRADE_LOCK_DAYS=8
DEFAULT_TRADING_MODE=DEMO
ALLOW_REAL_TRADING=false
DEMO_INITIAL_BALANCE=100000
DEMO_CURRENCY=RUB
MANUAL_RUB_USD_RATE=70.8
DMARKET_DYNAMIC_TITLE_LIMIT=160
DMARKET_EXTRA_TITLES=
CSGO_MARKET_PRICE_HISTORY_INDEX_ENDPOINT=/api/v2/full-history/all.json
CSGO_MARKET_PRICE_HISTORY_ITEM_ENDPOINT=/api/v2/full-history/{item_id}.json
```

`DMARKET_EXTRA_TITLES` нужен для предметов, которые ты хочешь проверять всегда, даже если они не попали в автоматический топ buy orders. Пример:

```env
DMARKET_EXTRA_TITLES=Kukri Knife | Blue Steel (Battle-Scarred)
```

Для DMarket публичный API отдаёт цену в USD, поэтому `MANUAL_RUB_USD_RATE` должен примерно совпадать с курсом, который ты видишь на DMarket. Если курс стоит `100`, предмет за `$81.48` будет считаться как `8148 ₽` и такой оффер не пройдёт фильтр прибыли.

## 7. Безопасность

- Не вставляй токены и API-ключи в код.
- Все секреты хранятся только в `.env`.
- Доступ к боту разрешен только пользователю из `AUTHORIZED_TELEGRAM_ID`.
- По умолчанию работает `DEMO`.
- При `ALLOW_REAL_TRADING=false` REAL-режим не включится.
- Реальные операции требуют ручного подтверждения в Telegram.

## 8. Проверка тестами

```bash
pytest
```

Если на Windows pytest не может создать временную папку, запусти так:

```bash
pytest -q --basetemp .pytest_tmp
```
