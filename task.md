# FunPayBot — Procurement Automation (self-hosted)

## Problem Statement

Companies that buy cheap digital accounts on FunPay lose hours on manual work: a manager hunts for a suitable lot, clarifies details with the seller in chat, pays, copies the delivered credentials somewhere, and — when an account gets blocked — chases the seller for a refund/replacement. The process is slow, error-prone, and the purchased accounts end up scattered instead of in one auditable place. FunPayBot is a self-hosted product (admin + manager roles) that automates the cheap-purchase pipeline end-to-end: search → clarify → buy → store → support.

## Key Hypothesis

We believe that a self-hosted панель (Next.js) + Telegram bot wired to an authorized FunPay account will let a manager go from "find a lot" to "credentials stored in the accounts DB" in minutes instead of tens of minutes — and make blocked-account refunds traceable.
We'll know we're right when the median time from lot-found to credentials-in-DB drops below ~3 minutes and every purchased account has a chat link + status for dispute handling.

## Users

**Primary Users**:
- **Manager** — searches lots **in the panel**, talks to sellers and runs the buy flow **via the Telegram bot** (routed to them by allowlist), confirms delivered credentials, handles problem accounts.
- **Admin** — same as manager plus: manages users/roles, FunPay & Telegram credentials, forbidden-word lists, sees the full accounts DB and audit, and **executes the actual payment in Telegram** using the FunPay-sourced payment link.

**Job to Be Done**: When I need to buy a cheap FunPay account, I want to find a verified lot, confirm details with the seller, pay, and have the delivered credentials land in our database automatically, so I can resell/use them and reclaim refunds when they break.

**Non-Users**: FunPay *sellers* (this is the buyer side); end customers; anyone outside the company (self-hosted, internal tool).

## Solution

A self-hosted, Dockerized system in three parts:

1. **web — Next.js личный кабинет**: auth + roles (admin/manager), **lot search (the ported parser — this is where managers search)**, the **accounts database** (credentials + chat link + status), and configuration.
2. **funpay-api** (Python + `FunPayAPI`): the only component holding the FunPay account session (golden_key) — sends/receives seller chat messages and performs purchases. The HTML lot parser (ported from `ai-router`) also lives here so all FunPay traffic is centralized. Global throttle: **≤ 100 actions/minute** to protect the single account.
3. **Telegram bot**: the manager's interaction surface for the live loop — seller-chat relay (routed per-manager via allowlist), credential-confirmation, and "message the seller" for problem accounts. **Payment**: the bot forwards the **payment link obtained from FunPay** into Telegram, and the **admin performs the USDT payment there**.

The lot parser is ported from the existing `ai-router` implementation: `lib/funpay-parser.ts` (fetch + regex scrape of FunPay lots, filters by query/price/min-reviews/forbidden-words, SSE progress) and the warranty extractor (`fetchFunpayWarranty`). It stays scoped to the current category (`lots/1355/`). Searching needs no FunPay login; buying and chat do.

### MVP Scope

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Auth + roles (admin, manager) | Multi-user internal tool; admin manages config |
| Must | Port FunPay lot parser into the stack — search in the **panel** by query, price, min-reviews, forbidden words; SSE progress; fixed category `lots/1355/` | Core "find a lot" step; already exists in ai-router |
| Must | Warranty/гарантия extraction per lot | Avoid buying no-warranty accounts; already exists |
| Must | funpay-api: FunPay session via golden_key + send/receive seller chat messages; global throttle ≤ 100 actions/min | Enables clarification + dispute messaging; protects the account |
| Must | Telegram bot: relay seller chat ↔ manager with **per-manager routing (allowlist)**, notify on new messages | Manager's live interface |
| Must | Accounts DB (web): credential record + FunPay chat link + status (active/blocked/refunded) + who/when | The durable output; auditable storage |
| Must | Credential capture: **bot pre-fills** delivered credentials from the seller's chat message → manager **confirms** → accounts DB | The "store" step, manager-in-the-loop |
| Must | docker-compose stack (web + funpay-api + Telegram worker + DB) | Self-hosted deployment |
| Should | Purchase action via funpay-api (place order on a lot) | Automate the buy itself, not just chat |
| Should | Payment: bot forwards the **FunPay-sourced payment link** to Telegram; **admin pays in USDT** there | Admin-in-the-loop payment, link from FunPay |
| Should | "Problem account" flow: from a DB record, message the seller via Telegram for refund/replacement | Reclaim value on blocks |
| Should | Audit log of actions (search, buy, message, status change) | Traceability for a team tool |
| Won't (MVP) | Auto-confirming credentials without a manager | Bot pre-fills, but a human always confirms |
| Won't (MVP) | Multiple FunPay accounts | User confirmed: single account |
| Won't (MVP) | Multiple/arbitrary lot categories | Keep fixed `lots/1355/` for MVP |
| Won't (MVP) | Custom crypto gateway / auto-payment | Payment link comes from FunPay; admin pays manually |
| Won't (MVP) | Reselling/fulfillment to end customers | Out of scope — procurement only |

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Time: lot-found → credentials-in-DB | < 3 min median | Timestamps on account records |
| Manual copy-paste steps per purchase | 0 (credentials confirmed, not retyped) | Workflow review |
| Problem accounts with refund/replacement attempted | 100% have a logged seller contact | Audit log on blocked records |
| Parser parity with ai-router | Same results on same query | Diff against ai-router output |

## Decisions (resolved 2026-06-03)

- ✅ **Search surface**: managers search lots **in the Next.js panel**. Telegram is only the live chat/buy loop.
- ✅ **Payment**: the payment link is **sourced from FunPay**; the bot forwards it to Telegram; the **admin performs the USDT payment** there. No custom crypto gateway.
- ✅ **FunPay library**: **Python `FunPayAPI`** (as used by FunPayCardinal) → funpay-api is a Python service.
- ✅ **Credential capture**: the **bot pre-fills** credentials from the seller's chat message; the **manager confirms** before they're saved.
- ✅ **Parser scope**: keep the **single fixed category `lots/1355/`** (no generalization in MVP).
- ✅ **Telegram model**: **per-manager routing via allowlist** (managers mapped to Telegram user IDs).
- ✅ **Throttle**: global cap of **≤ 100 actions/minute** in funpay-api.

## Open Questions

- [ ] Exact credential format(s) sellers deliver — affects how reliably the bot can pre-fill (fallback: free-text field the manager edits).
- [ ] Does FunPay expose a stable payment link the bot can capture programmatically, or must the admin open the order page? (Verify during Phase 6 — candidate for a risk spike.)

## Implementation Phases

| # | Phase | Description | Status | Depends |
|---|-------|-------------|--------|---------|
| 1 | Foundation | docker-compose skeleton (web + funpay-api + db); Next.js auth + admin/manager roles; settings for FunPay & Telegram credentials | pending | - |
| 2 | Port parser | Move `funpay-parser.ts` + warranty extractor into the stack; lot-search UI **in the panel** with SSE progress; query/price/min-reviews/forbidden-word filters; fixed category `lots/1355/` | pending | 1 |
| 3 | FunPay session + chat | funpay-api (Python `FunPayAPI`) logs in with golden_key; send/receive seller messages; global throttle ≤ 100/min | pending | 1 |
| 4 | Telegram bridge | Telegram bot relays seller chat ↔ manager; per-manager routing + allowlist; new-message notifications | pending | 3 |
| 5 | Accounts DB | Account records (credentials, chat link, status, audit); bot pre-fills credentials from chat → manager confirms → DB | pending | 3 |
| 6 | Buy + payment (Should) | Purchase action via funpay-api; capture FunPay payment link → Telegram → admin pays in USDT; problem-account → seller-message flow | pending | 4,5 |

---
*Generated: 2026-06-03*
*Status: DRAFT - needs validation (see Open Questions)*
