# UNIRAJ GUESS PAPERS — Telegram Bot

A separate Telegram bot project for Rajasthan University Guess Papers. This repository is independent of the existing bot and repository.

## Current implementation status

- Telegram menu: Buy, Search, My Orders, Help, About
- Course / semester / subject / paper catalog
- Admin PDF upload with configurable price
- Two-admin support through `ADMIN_IDS`
- SQLite order history
- Health endpoint for hosting checks
- **Payments are intentionally disabled.** There is no fake payment-success path and no automatic PDF delivery until a trustworthy, production-suitable payment provider and its verification contract are approved and configured.

## Critical YouPI PG warning

The upstream YouPI PG repository describes itself as an experimental research/learning project, not certified, bank-approved, audited, or production-ready. It warns against relying on it for business-critical payments and says payment status must be independently reconciled against official bank records. This project therefore does not enable live real-money checkout or treat an unverified callback as payment.

Before accepting real customer payments, have an adult/business owner review the applicable legal and merchant requirements and use a payment provider suitable for production. This starter does not make or verify payments.

## Required environment variables

- `BOT_TOKEN`: Telegram bot token (keep only in hosting secrets)
- `ADMIN_IDS`: two Telegram numeric user IDs, comma-separated
- `DATABASE_PATH`: persistent SQLite database path
- `PAPERS_DIR`: persistent PDF storage directory
- `PAYMENT_MODE`: remains `disabled` in this starter

Never commit tokens, payment keys, webhook secrets, customer data, or PDFs to GitHub.

## Run locally

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
# Fill BOT_TOKEN and ADMIN_IDS in your local environment; do not commit .env
python -m app.main
```

## Admin PDF upload

1. Admin sends `/addpaper`.
2. Admin sends a PDF document.
3. The PDF caption must be: `Course | Semester | Subject | Paper | Price`
4. Example: `BSc PCM | 3 | Physics | Optics | 49`

Use `/papers` to inspect the catalog and `/orders` to inspect recent orders.

## Hosting limitations

The included Render blueprint is only a deployment starting point. Free web services may sleep, have limited runtime, and may not provide durable local disk. SQLite and uploaded PDFs require persistent storage; do not deploy a document-selling service on ephemeral storage. Configure persistent storage before production use. Set secrets in the hosting dashboard, not in source files.

## Not live yet

This repository is a starter scaffold, not a production launch. Payment checkout, signed webhook verification, idempotent fulfillment, durable file storage, PDF preview/watermark generation, and end-to-end deployment still require completion and review.
