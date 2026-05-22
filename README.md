# CS2 LIS-SKINS -> CSGO Market Signal Bot

Telegram-бот для ручного поиска арбитражных сигналов по CS2-скинам.

Текущая ветка ищет связки:

1. Купить предмет на `LIS-SKINS`.
2. Продать этот же предмет в уже существующий buy order на `CSGO Market`.
3. Прислать в Telegram самый выгодный сигнал с расчетом прибыли, ROI и ссылками на обе площадки.

Автоматическая покупка отключена. В `REAL`-режиме бот тоже не покупает на LIS-SKINS через API: он только показывает предупреждение и ссылку, а покупку ты делаешь вручную.

## Что изменено в этой версии

- Источник покупки по умолчанию: `LIS-SKINS`.
- Используется публичная выгрузка `https://lis-skins.com/market_export_json/csgo.json`.
- API-ключ LIS-SKINS не нужен для сканирования. Он нужен только если потом захочешь получать баланс через API.
- Цены LIS-SKINS в USD переводятся в рубли по курсу ЦБ РФ.
- Сканер сортирует кандидатов по максимальной чистой прибыли и присылает только топ `MAX_DEALS_PER_SCAN`.
- В Telegram-сообщении есть кнопки-ссылки на LIS-SKINS и CSGO Market.
- После `Скрыть сделку` или `Отметить как куплено` сообщение с оффером удаляется из чата.

## Локальный запуск на компьютере

Нужен Python `3.11+`.

```powershell
python --version
```

Установка на Windows:

```powershell
cd "C:\Users\rwdra\Desktop\temka cs-lisskins"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python -m app.main
```

Минимально заполни в `.env`:

```env
TELEGRAM_BOT_TOKEN=токен_от_BotFather
AUTHORIZED_TELEGRAM_ID=твой_telegram_id
BUY_MARKET_SOURCE=LIS_SKINS
DEFAULT_TRADING_MODE=DEMO
ALLOW_REAL_TRADING=false
```

Для реального сканирования оставь:

```env
USE_MOCK_MARKETS=false
```

Для теста без реальных маркетов можно включить:

```env
USE_MOCK_MARKETS=true
SCAN_INTERVAL_SECONDS=60
```

После запуска открой Telegram и напиши боту:

```text
/start
/status
/deals
/best
/settings
```

## Основные настройки

```env
MIN_PROFIT_PERCENT=5
MIN_PROFIT_ABSOLUTE=100
MIN_ITEM_PRICE=300
MAX_ITEM_PRICE=50000
MAX_DEALS_PER_SCAN=5
MIN_LIQUIDITY_SCORE=60
SCAN_INTERVAL_SECONDS=300

LIS_SKINS_FEE_PERCENT=0
CSGO_MARKET_FEE_PERCENT=5
WITHDRAWAL_FEE_PERCENT=0

RUB_USD_RATE_SOURCE=CBR
CURRENCY_RATE_FALLBACK_TO_MANUAL=true
MANUAL_RUB_USD_RATE=100
```

`MAX_ITEM_PRICE` отвечает за верхний лимит цены предмета. Например, если хочешь искать только до 15 000 ₽:

```env
MAX_ITEM_PRICE=15000
```

## Запуск на VPS через screen

Пример для Ubuntu/Debian:

```bash
ssh root@SERVER_IP
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git screen
```

Клонирование именно этой версии:

```bash
git clone -b codex/lisskins-market-scanner https://github.com/RwDragon111/cs2.git cs2-lisskins
cd cs2-lisskins
```

Установка:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
mkdir -p data logs
```

Запуск в `screen`:

```bash
screen -S cs2-lisskins
source .venv/bin/activate
python -m app.main
```

Выйти из `screen`, не останавливая бота:

```text
Ctrl+A, потом D
```

Вернуться в сессию:

```bash
screen -r cs2-lisskins
```

Остановить бота внутри screen:

```text
Ctrl+C
```

## Docker

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

## Безопасность

- Секреты хранятся только в `.env`.
- Бот принимает команды только от `AUTHORIZED_TELEGRAM_ID`.
- По умолчанию включен `DEMO`.
- `ALLOW_REAL_TRADING=false` блокирует реальные действия.
- В этой ветке LIS-SKINS покупка через API не реализована намеренно: бот присылает ссылку, а решение принимаешь вручную.

## Проверки

```bash
python -m compileall app
pytest -q
```
