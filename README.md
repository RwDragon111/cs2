# CS2 Arbitrage Bot MVP

Python-приложение для мониторинга арбитражных возможностей на CS2-скинах между Market.CSGO и LIS-SKINS.

MVP работает без Docker, PostgreSQL, Redis и Celery. Реальные покупки и продажи отключены: доступны только режимы `SIGNAL_ONLY` и `PAPER_TRADING`.

## Что делает бот

Бот получает листинги рынков, нормализует названия предметов, считает цену в RUB/USD, учитывает комиссии, payment fees, конвертацию, risk buffer, ликвидность и фильтры риска. Если сделка проходит условия, бот отправляет сигнал в Telegram или пишет его в консоль и `logs/app.log`.

Основной поток:

```text
Market.CSGO + LIS-SKINS или mock-данные
-> нормализация предметов
-> расчёт RUB/USD
-> комиссии и payment compatibility
-> liquidity score
-> risk filters
-> opportunity detection
-> Telegram/log signal
-> Paper Buy
-> виртуальный trade ban 7 дней
-> Paper Sell
-> actual PnL
```

## Архитектура проекта

```text
app/
  config.py                 # настройки из .env
  logging_config.py          # консоль + logs/app.log
  core/                      # enums и exceptions
  db/                        # SQLite + SQLAlchemy models/repositories
  markets/                   # Market.CSGO, LIS-SKINS, mock connectors
  normalizer/                # нормализация названий предметов
  currency/                  # RUB/USD engine
  pricing/                   # комиссии, ROI, net profit
  liquidity/                 # liquidity score
  risk/                      # blacklist и risk filters
  opportunities/             # поиск арбитража
  paper_trading/             # virtual account, positions, Paper Buy/Sell
  telegram_bot/              # Telegram notifier, handlers, command menu
  scheduler/                 # фоновые asyncio loops
  utils/                     # money/time/retry helpers
```

SQLite-файл создаётся автоматически: `data/cs2_arbitrage.db`.

## Почему Market.CSGO и LIS-SKINS

В базовой версии используются только Market.CSGO и LIS-SKINS, потому что MVP ориентирован на RUB и платежи, подходящие пользователю из России.

White.Market исключён из базовой версии. Waxpeer не включён по умолчанию из-за риска RUB -> USD конвертации и дополнительных комиссий. CS.MONEY запрещён полностью и не используется ни для покупки, ни для продажи, ни для сравнения цен, ни как источник fair price или market index.

Третий рынок можно добавить только отдельным connector-ом после проверки: RUB, российские карты, MIR/YooMoney, конвертация, комиссии, официальный API, ликвидность, репутация и blacklist.

## Paper Trading

Стартовый виртуальный депозит: `10 000 ₽`.

Paper Buy:

1. Повторно проверяет, что listing ещё доступен.
2. Повторно получает актуальную цену.
3. Пересчитывает комиссии и ROI.
4. Проверяет virtual balance.
5. Создаёт виртуальную позицию.
6. Списывает `total_cost_rub`.
7. Ставит статус `TRADE_LOCKED`.
8. Ставит `trade_ban_until = bought_at + 7 days`.

Paper Sell:

1. Разрешён только после окончания trade ban.
2. Берёт текущую цену предмета на целевом рынке.
3. Считает комиссию продажи и withdrawal fee.
4. Возвращает чистую выручку на paper balance.
5. Фиксирует `actual_profit_rub` и `actual_roi_percent`.

Главная аналитика стратегии: сравнение `expected_profit` в момент сигнала и `actual_profit` после 7-дневного trade ban.

## Расчёт прибыли

```text
net_profit =
    expected_sell_price
    - sell_market_fee
    - buy_price
    - buy_market_fee
    - deposit_fee
    - withdrawal_fee
    - currency_conversion_fee
    - expected_slippage
    - risk_buffer
```

```text
roi_percent = net_profit / total_cost * 100
```

Базовая валюта расчёта - RUB. USD считается дополнительно через `MANUAL_RUB_USD_RATE`.

## Быстрый локальный запуск

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

На Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

## Установка на пустой VPS с нуля

Ниже команды для Ubuntu/Debian. Выполняй их на сервере по SSH.

### 1. Обновить систему

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Поставить базовые пакеты

```bash
sudo apt install -y python3 python3-venv python3-pip git screen ca-certificates curl nano
```

Проверить Python:

```bash
python3 --version
```

Рекомендуется Python 3.11+, но проект совместим и с Python 3.10, который часто стоит по умолчанию на Ubuntu 22.04.

### 3. Скачать проект

Вариант A: через GitHub:

```bash
cd /opt
sudo git clone https://github.com/RwDragon111/cs2_arbitrage.git cs2_arbitrage_bot
sudo chown -R "$USER":"$USER" /opt/cs2_arbitrage_bot
cd /opt/cs2_arbitrage_bot
```

Вариант B: если папка проекта загружается с компьютера:

```bash
sudo mkdir -p /opt/cs2_arbitrage_bot
sudo chown -R "$USER":"$USER" /opt/cs2_arbitrage_bot
cd /opt/cs2_arbitrage_bot
```

Затем загрузи файлы проекта в `/opt/cs2_arbitrage_bot`, например через `scp`, SFTP или панель хостинга.

### 4. Создать виртуальное окружение

```bash
cd /opt/cs2_arbitrage_bot
python3 -m venv venv
source venv/bin/activate
```

### 5. Установить зависимости

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Создать `.env`

```bash
cp .env.example .env
nano .env
```

Минимальный безопасный старт без Telegram и без API-ключей:

```env
USE_MOCK_MARKETS=true
TELEGRAM_ENABLED=false
TRADING_MODE=PAPER_TRADING
PAPER_TRADING_INITIAL_BALANCE_RUB=10000
```

Старт с Telegram:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:telegram_token
TELEGRAM_ADMIN_CHAT_ID=123456789
```

Если `USE_MOCK_MARKETS=true` или API-ключи пустые, бот работает на mock-данных. Это нормальный режим для первой проверки.

### 7. Проверить запуск

```bash
python main.py
```

Если всё нормально, останови `Ctrl+C`.

### 8. Запустить через screen

```bash
screen -S cs2-arb
cd /opt/cs2_arbitrage_bot
source venv/bin/activate
python main.py
```

Отсоединиться от screen, чтобы бот продолжал работать:

```text
Ctrl+A, затем D
```

Вернуться в окно:

```bash
screen -r cs2-arb
```

Остановить бота внутри screen:

```text
Ctrl+C
```

Закрыть screen-сессию после остановки:

```bash
exit
```

Посмотреть список screen-сессий:

```bash
screen -ls
```

Если нужно убить зависшую сессию:

```bash
screen -S cs2-arb -X quit
```

## Запуск через tmux

```bash
tmux new -s cs2-arb
cd /opt/cs2_arbitrage_bot
source venv/bin/activate
python main.py
```

Отсоединиться:

```text
Ctrl+B, затем D
```

Вернуться:

```bash
tmux attach -t cs2-arb
```

## Systemd service

Создать unit:

```bash
sudo nano /etc/systemd/system/cs2-arbitrage.service
```

Содержимое:

```ini
[Unit]
Description=CS2 Arbitrage Bot
After=network.target

[Service]
WorkingDirectory=/opt/cs2_arbitrage_bot
ExecStart=/opt/cs2_arbitrage_bot/venv/bin/python main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cs2-arbitrage
sudo systemctl start cs2-arbitrage
sudo systemctl status cs2-arbitrage
```

Логи:

```bash
sudo journalctl -u cs2-arbitrage -f
```

Остановка:

```bash
sudo systemctl stop cs2-arbitrage
```

## Telegram

Если Telegram включён, бот регистрирует меню команд в клиенте Telegram. Кнопка меню слева снизу покажет все команды с описаниями.

Команды:

```text
/start - запуск и краткое описание
/status - общий статус
/balance - текущий paper-баланс
/opportunities - активные opportunities
/last - последние opportunities
/settings - настройки режима
/blacklist - blacklist и запрещённые рынки
/pnl - PnL
/positions - paper-позиции
/pause - зарезервировано
/resume - зарезервировано
/payment_status - payment compatibility
/markets - подключённые рынки
/paper_status - полный статус Paper Trading
/paper_balance - виртуальный баланс
/paper_positions - виртуальные позиции
/paper_open - открытые позиции
/paper_ready - готовые к продаже позиции
/paper_sold - проданные позиции
/paper_pnl - Paper Trading аналитика
/paper_reset - зарезервировано
/paper_settings - настройки Paper Trading
/paper_buy <opportunity_id> - виртуальная покупка
/paper_sell <position_id> - виртуальная продажа
/help - список команд
```

Если Telegram выключен, сигналы пишутся в консоль и `logs/app.log`.

## Реальные API

Market.CSGO connector держит endpoint-ы в одном месте:

- `https://market.csgo.com/api/v2/prices/RUB.json`
- `https://market.csgo.com/api/full-export/RUB.json`
- `https://market.csgo.com/api/v2/full-history/all.json`

У LIS-SKINS API может требовать авторизацию и формат может отличаться от публичных примеров. Поэтому endpoint-ы изолированы в `LisSkinsConnector.LISTINGS_ENDPOINT` и `BALANCE_ENDPOINT`; если формат API отличается, правится только connector.

## Подготовка к публикации на GitHub

В репозиторий должны попадать исходники, тесты, README, `.env.example`, `.gitignore`, `requirements.txt`.

Не публиковать:

```text
.env
venv/
.venv/
data/*.db
logs/*.log
__pycache__/
.pytest_cache/
```

Эти пути уже добавлены в `.gitignore`.

## Тесты

```bash
pytest
```

## Риски

Арбитраж на скинах не гарантирует прибыль. Основные риски: изменение цены за 7 дней trade ban, низкая ликвидность, исчезновение listing, скрытые комиссии, курсовой spread, задержки вывода, ограничения рынков, неверные API-данные и false positive. Поэтому MVP намеренно работает без реальных покупок и продаж.
