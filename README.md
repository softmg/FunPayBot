# FunPayBot Procurement Automation

Self-hosted procurement automation for FunPay account purchasing.

## Services

- `apps/web` — Next.js admin and manager panel (auth, lot search, accounts DB, admin settings).
- `services/funpay-api` — FastAPI service that centralizes FunPay parsing, chat, purchase actions, and throttling.
- `services/telegram-bot` — Telegram worker for manager/admin live workflows (seller chat relay, credential confirmation).
- `packages/db` — SQL migrations for Postgres.

## Quick Start

1. Copy `.env.example` to `.env` and fill the secrets.
2. Run:

```powershell
docker compose up --build
```

3. Open `http://localhost:3000`.
4. Login with `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` (auto-creates admin on first login).

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│  web     │────▶│  funpay-api  │◀────│ telegram │
│ (Next.js)│     │  (FastAPI)   │     │   bot    │
└────┬─────┘     └──────┬───────┘     └────┬─────┘
     │                  │                  │
     └──────────┬───────┘──────────────────┘
                │
          ┌─────▼─────┐
          │ Postgres  │
          └───────────┘
```

## Web Panel Features

- **Auth**: HMAC-signed session cookies, admin/manager roles, Next.js middleware protection.
- **Lot Search**: Query FunPay lots/1355/ by keyword, price, reviews, forbidden words. DB forbidden words are auto-merged.
- **Accounts DB**: Interactive table with status management (active/blocked/replacement_requested/refunded), contact-seller flow for problem accounts.
- **Admin Panel**: User CRUD (create managers, toggle active, set Telegram IDs), forbidden words management, system settings (FunPay keys, Telegram token).

## Telegram Bot Commands

- `/start` — Show available commands.
- `/send <chat_id> <message>` — Send message to a FunPay seller.
- `/chats` — List your assigned FunPay chats.
- `/assign <chat_id> <telegram_id>` — Assign a chat to a manager (admin only).
- Credential auto-detection: paste `login:password` and confirm via inline button.

The bot runs a background poller that fetches new seller messages from FunPay and relays them to the assigned manager on Telegram (configurable interval via `FUNPAY_POLL_INTERVAL_SECONDS`).

## FunPayAPI Integration

`services/funpay-api` vendors the `FunPayAPI` package from `sidor0912/FunPayCardinal` at commit `8b52a855f242da854806ef09ab1691b53d5d20a9`.

Implemented FunPay-backed endpoints:

- `GET /health`
- `GET /session`
- `POST /session/refresh`
- `GET /chats`
- `GET /chats/{chat_id}`
- `GET /chats/{chat_id}/history`
- `POST /chats/send`
- `POST /lots/search`
- `GET /lots/search/stream` (SSE)
- `GET /lots/warranty`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/refund`

`POST /orders` intentionally returns `501` until the buyer-side purchase/payment-link flow is verified against a live FunPay account.

## Testing

```powershell
# funpay-api
cd services/funpay-api; python -m pytest tests/ -v

# telegram-bot
cd services/telegram-bot; python -m pytest tests/ -v

# web typecheck
cd apps/web; npm run typecheck
```

## Configuration

All configurable values are in `.env` — see `.env.example` for the full list. Admin can also manage settings via the web panel at `/admin`.
