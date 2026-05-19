# CS2 Arbitrage Bot

Python MVP для мониторинга арбитража CS2-скинов без Docker, PostgreSQL, Redis и Celery.

Текущая рабочая схема:

```text
DMarket реальные публичные офферы
-> нормализация предмета
-> Market.CSGO публичные buy orders
-> расчет комиссий, RUB/USD, risk buffer и ликвидности
-> Telegram сигнал или лог
-> Paper Buy
-> виртуальный 7-дневный trade ban
-> Paper Sell по текущему buy order Market.CSGO
-> фактический PnL
```

Реальные покупки и продажи в MVP отключены. Бот ничего не покупает на DMarket и ничего не продает на Market.CSGO. Он только проверяет, сработала бы стратегия в Paper Trading.

## Что изменилось

- LIS-SKINS отключен из базового контура.
- DMarket включен как основной рынок покупки.
- Market.CSGO используется как рынок продажи через публичные buy orders, а не через обычные листинги.
- Mock-данные не используются по умолчанию.
- `USE_MOCK_MARKETS=true` нужен только для локальных тестов.
- Стартовый Paper Trading баланс: `10000 RUB`.

## Архитектура

```text
main.py
app/
  config.py                 # .env настройки
  logging_config.py         # консоль + logs/app.log
  db/                       # SQLAlchemy 2.x + SQLite
  markets/                  # DMarket, Market.CSGO buy orders, mock, optional connectors
  normalizer/               # нормализация market_hash_name
  currency/                 # RUB/USD и spread
  pricing/                  # net profit, fees, risk buffer
  liquidity/                # liquidity_score 0..100
  risk/                     # запреты, лимиты, blacklist
  opportunities/            # детектор DMarket -> Market.CSGO.BuyOrder
  paper_trading/            # Paper Buy, Paper Sell, trade ban, PnL
  telegram_bot/             # команды, кнопки, меню Telegram
  scheduler/                # фоновые polling loops
data/cs2_arbitrage.db       # SQLite создается автоматически
logs/app.log                # лог создается автоматически
tests/
```

## Как бот считает сигнал

1. Берет реальные офферы DMarket через публичный endpoint `exchange/v1/market/items`.
2. Берет реальные buy orders Market.CSGO через `api/v2/prices/orders/RUB.json`.
3. Находит одинаковые предметы по `normalized_name`.
4. Сравнивает минимальную цену покупки на DMarket с максимальным buy order на Market.CSGO.
5. Считает:
   - buy price;
   - sell price;
   - market fee;
   - payment fee;
   - currency conversion fee;
   - risk buffer;
   - expected net profit;
   - ROI;
   - liquidity score.
6. Отправляет сигнал только если проходят пороги `MIN_PROFIT_RUB`, `MIN_ROI_PERCENT`, `MIN_LIQUIDITY_SCORE` и лимиты риска.

Важно: Market.CSGO sell side здесь означает `Market.CSGO.BuyOrder`, то есть цену, по которой уже есть запрос на покупку.

## Paper Trading

По умолчанию:

```env
TRADING_MODE=PAPER_TRADING
PAPER_TRADING_ENABLED=true
PAPER_TRADING_INITIAL_BALANCE_RUB=10000
PAPER_TRADING_TRADE_BAN_DAYS=7
PAPER_TRADING_SELL_MODE=MANUAL_SELL
```

Paper Buy:

- повторно проверяет, что оффер DMarket еще есть;
- повторно берет текущий buy order Market.CSGO;
- пересчитывает прибыль;
- списывает виртуальный баланс;
- создает позицию;
- ставит статус `TRADE_LOCKED`;
- ставит trade ban на 7 дней.

Paper Sell:

- доступен только после trade ban;
- берет текущий buy order Market.CSGO;
- считает комиссию продажи;
- считает actual PnL;
- возвращает виртуальную выручку на paper balance;
- переводит позицию в `SOLD`.

## Установка на пустой VPS

Команды ниже рассчитаны на Ubuntu/Debian сервер.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip screen
python3 --version
```

Нужен Python 3.11+. Если на сервере Python старее 3.11, поставь более новый Python через пакеты твоего дистрибутива или обнови образ VPS до Ubuntu 24.04.

Склонировать проект:

```bash
cd /opt
sudo git clone https://github.com/RwDragon111/cs2_arbitrage.git cs2_arbitrage_bot
sudo chown -R "$USER":"$USER" /opt/cs2_arbitrage_bot
cd /opt/cs2_arbitrage_bot
```

Создать окружение и поставить зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Создать `.env`:

```bash
cp .env.example .env
nano .env
```

Минимальные настройки:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=сюда_токен_бота
TELEGRAM_ADMIN_CHAT_ID=сюда_твой_chat_id

USE_MOCK_MARKETS=false
ENABLE_DMARKET=true
ENABLE_MARKET_CSGO=true

TRADING_MODE=PAPER_TRADING
PAPER_TRADING_INITIAL_BALANCE_RUB=10000

MANUAL_RUB_USD_RATE=100
```

DMarket API key для текущего мониторинга не нужен: бот использует публичные рыночные офферы. Поля `DMARKET_PUBLIC_KEY` и `DMARKET_SECRET_KEY` оставлены под будущие подписанные методы, но реальные сделки в MVP все равно отключены.

Первый запуск:

```bash
python main.py
```

Если до этого запускалась старая версия с mock/LIS и в Telegram приходили старые фейковые сигналы, очисти старую SQLite-базу:

```bash
rm -f data/cs2_arbitrage.db
python main.py
```

## Запуск через screen

```bash
cd /opt/cs2_arbitrage_bot
source venv/bin/activate
screen -S cs2bot
python main.py
```

Отключиться от screen, не останавливая бота:

```text
Ctrl+A, потом D
```

Вернуться:

```bash
screen -r cs2bot
```

Остановить бота:

```text
Ctrl+C
```

Закрыть завершенную screen-сессию:

```bash
exit
```

Посмотреть сессии:

```bash
screen -ls
```

## Обновление на VPS

```bash
cd /opt/cs2_arbitrage_bot
git pull
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Если после обновления остались старые mock opportunities:

```bash
rm -f data/cs2_arbitrage.db
python main.py
```

## Telegram

Бот регистрирует меню команд в Telegram. Кнопка меню слева снизу показывает команды и описания.

Основные команды:

```text
/start - запуск и описание
/status - статус Paper Trading
/balance - paper balance
/opportunities - активные opportunities
/positions - paper positions
/dmarket_stats - последние офферы DMarket
/market_spreads - диагностика DMarket vs Market.CSGO buy orders
/paper_buy <opportunity_id> - Paper Buy вручную
/paper_sell <position_id> - Paper Sell вручную
/help - список команд
```

В сигналах также есть inline-кнопка `Paper Buy`.

## Режим без Telegram

В `.env`:

```env
TELEGRAM_ENABLED=false
```

Тогда сигналы будут писаться в консоль и `logs/app.log`.

## Важные настройки

```env
USE_MOCK_MARKETS=false
ENABLE_DMARKET=true
ENABLE_MARKET_CSGO=true

MIN_PROFIT_RUB=100
MIN_ROI_PERCENT=5.0
MAX_BUY_PRICE_RUB=10000
MIN_LIQUIDITY_SCORE=60

MARKET_POLL_INTERVAL_SECONDS=30
OPPORTUNITY_SCAN_INTERVAL_SECONDS=35

BASE_CURRENCY=RUB
SECONDARY_CURRENCY=USD
MANUAL_RUB_USD_RATE=100
CURRENCY_SPREAD_PERCENT=1.0
```

Если хочешь тестовые данные:

```env
USE_MOCK_MARKETS=true
```

Тогда бот будет использовать `Mock.DMarket` и `Mock.Market.CSGO.BuyOrder`. Это только для разработки.

## Безопасность

- API-ключи не хранятся в коде.
- `.env` не должен попадать в Git.
- Реальные `buy_item()` и `sell_item()` выбрасывают `RealTradingDisabledError`.
- `PAPER_TRADING` не вызывает реальные buy/sell API.
- `SIGNAL_ONLY` не вызывает реальные buy/sell API.
- CS.MONEY запрещен кодом и не используется вообще.
- White.Market запрещен.
- Waxpeer не включен в базовую версию.
- Перед Paper Buy цена и наличие проверяются повторно.
- Один listing нельзя купить дважды в открытых paper-позициях.
- Продажа до trade ban невозможна.

## Тесты

```bash
source venv/bin/activate
pytest
```

## Ограничения MVP

- Это не торговый автомат.
- Реальные покупки и продажи не реализованы.
- DMarket используется для публичных офферов покупки в Paper Trading.
- Market.CSGO используется как целевая сторона продажи по публичным buy orders.
- Курс RUB/USD по умолчанию ручной, настрой `MANUAL_RUB_USD_RATE`.
- Сигнал не гарантирует исполнение после 7-дневного trade ban: именно это и проверяет Paper Trading.
