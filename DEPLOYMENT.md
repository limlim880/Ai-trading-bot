# Stage 1: Deploying to Railway

This replaces ngrok with a permanent HTTPS URL that TradingView can send
webhooks to, and moves the SQLite database onto a persistent volume so it
survives deploys and restarts.

Follow every step in order. Each step tells you exactly what to click or
type, and what you should see when it worked.

---

## Step 1 — Push this code to GitHub

Railway deploys from a GitHub repository, so the code needs to be on GitHub
first.

1. Open a terminal in the project folder.
2. Run:
   ```bash
   git add .
   git commit -m "Baseline AI trading assistant + Stage 1 deployment files"
   git push -u origin claude/ai-trading-assistant-2920f4
   ```
3. **Expected output:** a line ending in something like
   `branch 'claude/ai-trading-assistant-2920f4' set up to track 'origin/claude/ai-trading-assistant-2920f4'.`
   and no red error text.

(If you're reading this after I've already pushed for you, skip to Step 2.)

---

## Step 2 — Create a Railway account and project

1. Go to **https://railway.app** in your browser.
2. Click **Login**, then choose **Login with GitHub**, and authorize
   Railway to access your GitHub account.
3. Once logged in, click **New Project**.
4. Choose **Deploy from GitHub repo**.
5. If asked, click **Configure GitHub App** and grant Railway access to the
   `limlim880/Ai-trading-bot` repository specifically (or "All repositories"
   if you prefer).
6. Select the `Ai-trading-bot` repository from the list.

**Expected result:** Railway creates a new project and immediately starts a
build. It will likely **fail or the app will crash-loop at this point** —
that's expected, because we haven't set the required environment variables
yet (Step 3) or added the persistent volume (Step 4). Don't worry about the
failed deploy yet.

---

## Step 3 — Set environment variables

1. Inside your new Railway project, click on the service (it will be named
   something like `Ai-trading-bot`).
2. Click the **Variables** tab.
3. Click **New Variable** and add each of the following one at a time
   (name on the left, value on the right):

   | Variable | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `WEBHOOK_SECRET` | a long random string — generate one by running `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` on your own machine and pasting the output here |
   | `DATABASE_PATH` | `/data/trading_assistant.db` |
   | `TELEGRAM_BOT_TOKEN` | your bot token from @BotFather |
   | `TELEGRAM_CHAT_ID` | your Telegram chat id |
   | `ACCOUNT_BALANCE` | `10000` (or your real account balance) |
   | `RISK_PER_TRADE_PERCENT` | `0.5` |
   | `MAX_DAILY_LOSS_PERCENT` | `1.0` |
   | `MAX_WEEKLY_LOSS_PERCENT` | `3.0` |
   | `MAX_CONCURRENT_TRADES` | `2` |
   | `MIN_RISK_REWARD` | `2.0` |
   | `MIN_SIGNAL_SCORE` | `75` |
   | `PENDING_SIGNAL_EXPIRY_HOURS` | `48` |
   | `WEBHOOK_MAX_AGE_SECONDS` | `300` |
   | `RATE_LIMIT_PER_MINUTE` | `30` |
   | `LOG_LEVEL` | `INFO` |

   Do **not** set `PORT` — Railway sets this automatically, and the app
   already reads it via the Dockerfile's `${PORT}`.

   **Write down the `WEBHOOK_SECRET` value somewhere safe** — you will
   paste it into your TradingView alert JSON later.

4. Railway automatically redeploys whenever you save a variable. Let it
   redeploy after adding the last one.

---

## Step 4 — Add a persistent volume for the database

Without this step, **your entire trade journal is wiped every time Railway
redeploys the app.** Do not skip it.

1. In your Railway project, click the service again.
2. Click the **Settings** tab.
3. Scroll to the **Volumes** section and click **New Volume**.
4. Set the **Mount path** to exactly: `/data`
5. Click **Add**.
6. Confirm the `DATABASE_PATH` variable from Step 3 is `/data/trading_assistant.db`
   — that path must live inside the `/data` mount you just created, or the
   database will still be wiped on every deploy.
7. Railway will redeploy the service again after adding the volume.

**Expected result:** after this redeploy, the **Deployments** tab shows a
green "Success" build, and the service status shows **Active**.

---

## Step 5 — Get your permanent HTTPS URL

1. Still in **Settings**, scroll to the **Networking** section.
2. Click **Generate Domain**.
3. Railway will show you a URL like:
   `https://ai-trading-bot-production-XXXX.up.railway.app`
4. Copy this URL — this is your app's permanent address. It replaces
   ngrok entirely.

---

## Step 6 — Verify the deployment

Open a terminal on your own machine (not inside Railway) and run, replacing
the URL with your real one:

```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/health
```

**Expected output:**
```json
{"status":"ok","database":true}
```

If you see `"database": true`, the app is running and can read/write the
persistent volume.

Next, test Telegram end-to-end:

```bash
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/test-telegram
```

**Expected output:** `{"sent":true}`, and a message should arrive in your
Telegram chat within a few seconds. If you get
`{"detail":"Telegram not configured or send failed"}`, double-check the
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` variables in Step 3.

Finally, confirm persistence survives a redeploy:

```bash
curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/tradingview-webhook \
  -H "Content-Type: application/json" \
  -d '{"secret":"YOUR_WEBHOOK_SECRET", ... }'
```
(use a copy of `sample_signal.json` with your real secret and a current
`timestamp`), then in the Railway dashboard click **Deploy → Redeploy** to
force a fresh container, then run:
```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/health
```
and separately check that a follow-up webhook with the same symbol/direction
still gets blocked as a duplicate — that proves the signal survived the
redeploy on the volume instead of being wiped.

---

## Step 7 — Point TradingView at the new URL

1. Open your TradingView alert (or create a new one on the Pine Script
   strategy).
2. In the alert's **Webhook URL** field, enter:
   `https://YOUR-RAILWAY-URL.up.railway.app/tradingview-webhook`
3. In the alert **Message** field, make sure the JSON body includes
   `"secret": "YOUR_WEBHOOK_SECRET"` matching Step 3's value.
4. Save the alert.
5. **You no longer need ngrok running.** You can close that terminal
   permanently.

---

## Troubleshooting

- **Build fails with "Dockerfile not found"** — confirm `Dockerfile` is
  committed at the repository root (not inside a subfolder).
- **App crash-loops with `WEBHOOK_SECRET not set`-style 500s on every
  webhook call** — you forgot Step 3; go set `WEBHOOK_SECRET`.
- **`/health` returns `"database": false`** — the volume isn't mounted at
  `/data`, or `DATABASE_PATH` doesn't point inside it. Re-check Step 4.
- **Telegram test fails** — token/chat id typo is the most common cause.
  Message your bot first (Telegram requires the user to have started a
  conversation with the bot before it can message back), then re-check the
  chat id with `https://api.telegram.org/bot<token>/getUpdates`.
