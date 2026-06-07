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

