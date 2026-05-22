# CS2 LIS-SKINS -> CSGO Market Signal Bot

Telegram-бот для ручного поиска арбитражных сигналов по CS2-скинам.

Схема:

1. Бот смотрит публичные офферы на `LIS-SKINS`.
2. Сравнивает их с buy orders на `CSGO Market`.
3. Присылает в Telegram лучшие сделки с прибылью, ROI и ссылками.

Автоматическая покупка отключена. Ветка рассчитана на ручную покупку: бот показывает сигнал, а решение принимаешь ты.

## Где хранятся настройки

`.env` теперь нужен только для токенов и API-ключей.

Фильтры и комиссии хранятся в JSON-файле:

```text
data/settings.json
```

Если файла нет, бот создаст его сам при старте. Пример лежит здесь:

```text
config/settings.example.json
```

Настройки можно менять прямо из Telegram:

```text
/settings
/settings_help
/set MIN_PROFIT_PERCENT 2
/set MAX_ITEM_PRICE 15000
/set USE_MOCK_MARKETS false
/rescan
```

## Локальный запуск на Windows

```powershell
cd "C:\Users\rwdra\Desktop\temka cs-lisskins"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
python -m app.main
```

Минимально заполни `.env`:

```env
TELEGRAM_BOT_TOKEN=токен_от_BotFather
AUTHORIZED_TELEGRAM_ID=твой_telegram_id
```

После запуска напиши боту:

```text
/start
/status
/deals
/inventory
/settings
```

## VPS через screen

```bash
ssh root@SERVER_IP
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git screen
git clone -b codex/lisskins-market-scanner https://github.com/RwDragon111/cs2.git cs2-lisskins
cd cs2-lisskins
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
mkdir -p data logs
screen -S cs2-lisskins
python -m app.main
```

Выйти из `screen`, не останавливая бота: `Ctrl+A`, потом `D`.

Вернуться:

```bash
screen -r cs2-lisskins
```

## Docker

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose logs -f
```

## Безопасность

- Секреты хранятся только в `.env`.
- Фильтры и комиссии хранятся в `data/settings.json`.
- Бот принимает команды только от `AUTHORIZED_TELEGRAM_ID`.
- По умолчанию включен `DEMO`.
- `ALLOW_REAL_TRADING=false` остается серверной защитой и не меняется через Telegram.
- LIS-SKINS покупка через API намеренно не реализована: бот присылает ссылку, покупка вручную.

## Проверки

```bash
python -m compileall app
pytest -q
```
