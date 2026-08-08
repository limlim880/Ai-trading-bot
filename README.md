# AI Trading Assistant Starter

This first version does not place trades.

It receives a TradingView-style signal, checks the strategy rules, calculates
demo risk, saves the signal in SQLite, and sends an alert through Telegram.

## 1. Install Python

Install Python 3.11 or newer.

During Windows installation, tick:

Add Python to PATH

## 2. Open this folder in Visual Studio Code

Open Visual Studio Code, select File, Open Folder, and choose this project.

## 3. Open the terminal

In Visual Studio Code, select Terminal, New Terminal.

## 4. Create a virtual environment

Windows PowerShell:

    python -m venv .venv
    .venv\Scripts\Activate.ps1

Windows Command Prompt:

    python -m venv .venv
    .venv\Scripts\activate.bat

Mac or Linux:

    python3 -m venv .venv
    source .venv/bin/activate

## 5. Install the packages

    python -m pip install --upgrade pip
    pip install -r requirements.txt

## 6. Create your private environment file

Make a copy of `.env.example` and name the copy `.env`.

Fill in:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- WEBHOOK_SECRET
- ADMIN_KEY

Do not share the `.env` file.

## 7. Run the app

    fastapi dev app.py

The terminal should show a local address similar to:

    http://127.0.0.1:8000

Open:

    http://127.0.0.1:8000/docs

## 8. Test Telegram

Inside the `/docs` page:

1. Open `POST /test-telegram`.
2. Click `Try it out`.
3. Enter your ADMIN_KEY in the `x-admin-key` field.
4. Click `Execute`.

Your Telegram bot should send a test message.

## 9. Test a trade signal

Open `sample_signal.json`.

Replace the `secret` value with the exact WEBHOOK_SECRET stored in `.env`.

In the `/docs` page:

1. Open `POST /tradingview-webhook`.
2. Click `Try it out`.
3. Paste the complete sample JSON into the request body.
4. Click `Execute`.

A qualifying setup should be saved and sent to Telegram.

## Safety design

- There is no broker connection.
- There is no order-placement code.
- All financial figures are demo calculations.
- Secrets stay in `.env`.
- Rejected signals are recorded for later review.
