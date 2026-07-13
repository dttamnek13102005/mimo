# Auto Login MiMo

This project runs as a background worker. It does not expose an HTTP port.

## Railway deployment

Railpack reads `railpack.json`, installs Chromium, and starts the nodriver worker
with `python app.py --headless`. Linux servers without a display automatically
enable headless mode as well.

Deploy `accounts.json` together with the source. Its structure is:

```json
{"interval_hours":4,"accounts":[{"account":"first@example.com","password":"secret"}]}
```

Set the token either in the uploaded `.env` file or as a Railway service
variable (the Railway variable takes precedence):

- `TELEGRAM_BOT_TOKEN`: Telegram bot token inserted into `prompt.txt` at runtime

Do not commit a populated `.env` file. It is ignored by Git.

## Local run

Set `TELEGRAM_BOT_TOKEN`, install `requirements.txt`, and run:

```powershell
python app.py --once
```
