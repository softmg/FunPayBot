# FunPay Automation MVP

MVP сервиса для автоматизации закупки аккаунтов на FunPay: поиск лотов, создание покупки, получение платежных реквизитов в Telegram, переписка с продавцом и сохранение полученных реквизитов аккаунта.

Проект собран как self-hosted система из web-панели, FastAPI-адаптера к FunPay, Telegram-бота и Postgres.

## Что реализовано

- Поиск лотов в категории FunPay с фильтрами по запросу, цене, отзывам и запрещенным словам.
- Просмотр гарантии по лоту.
- Выбор способа оплаты и создание заказа через FunPay.
- Передача платежной ссылки или crypto-реквизитов администраторам в Telegram.
- Telegram-бот для рабочих сценариев менеджера:
  - получение уведомлений по платежу;
  - отправка сообщений продавцу;
  - просмотр назначенных чатов;
  - подтверждение найденных реквизитов аккаунта.
- Админ-панель:
  - bootstrap первого администратора;
  - управление пользователями и Telegram ID;
  - управление запрещенными словами;
  - системные настройки.
- База аккаунтов с изменением статуса и сценарием обращения к продавцу по проблемному аккаунту.
- Аудит ключевых действий в Postgres.

## Сервисы

- `apps/web` - Next.js web-панель для администратора и менеджеров.
- `services/funpay-api` - FastAPI-сервис для работы с FunPay: поиск, чаты, заказы, возвраты.
- `services/telegram-bot` - Telegram worker для уведомлений, переписки и подтверждения реквизитов.
- `packages/db` - SQL-миграции Postgres.

## Требования

- Docker и Docker Compose.
- Telegram bot token.
- FunPay `golden_key` от аккаунта, с которого выполняются действия.

## Быстрый запуск

1. Скопируйте пример окружения:

```powershell
Copy-Item .env.example .env
```

2. Заполните `.env`:

```dotenv
NEXTAUTH_SECRET=replace-with-random-secret
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=change-me

FUNPAY_GOLDEN_KEY=...
FUNPAY_USER_AGENT=...

TELEGRAM_BOT_TOKEN=...
ADMIN_TELEGRAM_IDS=123456789

# Общий секрет для запросов web/telegram-bot -> funpay-api
INTERNAL_API_TOKEN=replace-with-random-token
```

Сгенерировать надежный секрет (32 байта в hex):

```powershell
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
```

или через `openssl rand -hex 32` (Linux/macOS).

3. Запустите сервисы:

```powershell
docker compose up --build
```

4. Откройте web-панель:

```text
http://localhost:3000
```

5. Войдите через `BOOTSTRAP_ADMIN_EMAIL` и `BOOTSTRAP_ADMIN_PASSWORD`. Первый администратор создается автоматически при первом входе.

## Переменные окружения

Полный список находится в `.env.example`.

Основные переменные:

- `DATABASE_URL` - подключение к Postgres.
- `NEXTAUTH_SECRET` - секрет для подписи session cookie.
- `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` - учетные данные первого администратора.
- `FUNPAY_GOLDEN_KEY` - FunPay session key.
- `FUNPAY_USER_AGENT` - User-Agent браузера, связанный с FunPay-сессией.
- `FUNPAY_BASE_URL` - базовый URL FunPay, по умолчанию `https://funpay.com`.
- `FUNPAY_CATEGORY_PATH` - категория поиска, по умолчанию `lots/1355/`.
- `FUNPAY_MAX_ACTIONS_PER_MINUTE` - лимит действий к FunPay.
- `TELEGRAM_BOT_TOKEN` - токен Telegram-бота.
- `ADMIN_TELEGRAM_IDS` - список Telegram ID администраторов через запятую.
- `FUNPAY_POLL_INTERVAL_SECONDS` - интервал опроса сообщений FunPay.
- `FUNPAY_API_URL` - внутренний URL FastAPI-сервиса.
- `INTERNAL_API_TOKEN` - общий секрет для запросов `web`/`telegram-bot` к `funpay-api`. Если не задан, `funpay-api` работает без аутентификации (в логах при старте выводится предупреждение). Сгенерируйте надежное значение, например `openssl rand -hex 32`.

Не коммитьте реальный `.env`: в нем находятся токены, cookie/session keys и другие секреты.

В production обязательно задайте надежные `NEXTAUTH_SECRET` и `INTERNAL_API_TOKEN`: при `NODE_ENV=production` web-панель откажется запускаться с плейсхолдером `NEXTAUTH_SECRET` (например `replace-me`), чтобы исключить подделку сессий. Postgres и `funpay-api` публикуются только на `127.0.0.1`; наружу смотрит лишь web на порту `3000` (разместите его за reverse-proxy с TLS).

## Основной сценарий

1. Администратор заходит в web-панель.
2. Ищет подходящий лот FunPay.
3. Открывает покупку и выбирает доступный способ оплаты.
4. Система создает заказ через FunPay и отправляет платежную ссылку или реквизиты в Telegram.
5. Менеджер оплачивает заказ и общается с продавцом через Telegram-бота.
6. Когда продавец присылает данные аккаунта, бот распознает формат `login:password` и предлагает подтвердить сохранение.
7. Подтвержденные реквизиты появляются в базе аккаунтов web-панели.

Этот сценарий был проверен вручную end-to-end: покупка создается, платежные реквизиты приходят в Telegram, сообщение продавцу отправляется.

## Telegram-команды

- `/start` - список доступных команд.
- `/send <chat_id> <message>` - отправить сообщение продавцу в FunPay.
- `/chats` - показать назначенные менеджеру чаты.
- `/assign <chat_id> <telegram_user_id>` - назначить чат менеджеру, доступно администратору.

Также бот обрабатывает сообщения с реквизитами аккаунта и предлагает сохранить их через inline-подтверждение.

## API FunPay-сервиса

Основные endpoints:

- `GET /health`
- `GET /session`
- `POST /session/refresh`
- `POST /lots/search`
- `GET /lots/search/stream`
- `GET /lots/warranty`
- `GET /chats`
- `GET /chats/messages`
- `GET /chats/{chat_id}`
- `GET /chats/{chat_id}/history`
- `POST /chats/send`
- `POST /orders/payment-methods`
- `POST /orders`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/refund`

`services/funpay-api` использует vendored `FunPayAPI` из `sidor0912/FunPayCardinal` на commit `8b52a855f242da854806ef09ab1691b53d5d20a9`.

## Проверки

Python-сервисы:

```powershell
cd services/funpay-api
python -m ruff check .
python -m pytest tests/ -v

cd ../telegram-bot
python -m ruff check .
python -m pytest tests/ -v
```

Web:

```powershell
cd apps/web
npm install
npm run typecheck
npm test
```

## Известные ограничения

- Это MVP тестового задания, а не полностью отполированный production-продукт.
- Основной happy path проверен вручную, но покрытие edge cases FunPay и платежных провайдеров нужно расширять.
- UX/UI web-панели требует дальнейшей полировки.
- Сценарии ошибок оплаты, изменения HTML FunPay и нестабильности внешних сервисов требуют дополнительного hardening.
- Раздел «Системные настройки» админ-панели сохраняет значения в БД, но `funpay-api` и `telegram-bot` читают конфигурацию из переменных окружения при старте; из БД сейчас потребляются только Telegram-настройки (`telegram_bot_token`, `admin_telegram_ids`). Смену `golden_key`/лимитов выполняйте через `.env` и перезапуск.
- Реквизиты аккаунтов хранятся в БД в открытом виде; для production добавьте шифрование на уровне приложения и ограничьте доступ к БД.
- Для production-эксплуатации нужны более строгая observability, алерты, backup/restore и полноценный секрет-менеджмент.
