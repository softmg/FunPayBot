# FunPayBot Procurement Automation

Self-hosted procurement automation for FunPay account purchasing.

## Services

- `apps/web` - Next.js admin and manager panel.
- `services/funpay-api` - FastAPI service that centralizes FunPay parsing, chat, purchase actions, and throttling.
- `services/telegram-bot` - Telegram worker for manager/admin live workflows.
- `packages/db` - SQL migrations for Postgres.

## Quick Start

1. Copy `.env.example` to `.env` and fill the secrets.
2. Run:

```powershell
docker compose up --build
```

3. Open `http://localhost:3000`.

The scaffold is intentionally conservative: FunPay purchase/chat methods are isolated behind adapters so the live API behavior can be verified without spreading FunPay session handling into the web or Telegram services.

## FunPayAPI Integration

`services/funpay-api` vendors the `FunPayAPI` package from `sidor0912/FunPayCardinal` at commit `8b52a855f242da854806ef09ab1691b53d5d20a9`.

Implemented FunPay-backed endpoints:

- `GET /session`
- `POST /session/refresh`
- `GET /chats`
- `GET /chats/{chat_id}`
- `GET /chats/{chat_id}/history`
- `POST /chats/send`
- `GET /orders/{order_id}`
- `POST /orders/{order_id}/refund`

`POST /orders` intentionally returns `501` until the buyer-side purchase/payment-link flow is verified against a live FunPay account.
