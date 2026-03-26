# Instagram-API

Heroku-deployable Instagram profile picture API built with Flask + Instaloader.

It uses an Instaloader session file for authenticated requests, downloads each profile picture locally, and serves the image directly from API with a **3-hour** cache.

## Endpoint

- `GET /api/pfp/<username>`

### Example response

- Returns image bytes (JPEG/PNG/WEBP based on source).
- Response headers:
	- `X-Cache: HIT|MISS`
	- `X-Cache-Expires-At: <UTC ISO timestamp>`

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create an Instaloader session file on your machine:

```bash
instaloader --login YOUR_INSTAGRAM_LOGIN --no-pictures --no-videos --no-video-thumbnails --no-compress-json
```

This creates a file like `session-YOUR_INSTAGRAM_LOGIN` in your current directory.

4. Run the API:

```bash
export INSTAGRAM_LOGIN_USER=YOUR_INSTAGRAM_LOGIN
export INSTAGRAM_SESSION_FILE=/absolute/path/to/session-YOUR_INSTAGRAM_LOGIN
python app.py
```

5. Test:

```bash
curl -i http://127.0.0.1:5000/api/pfp/instagram -o instagram_pfp.jpg
```

## Heroku deployment (manual via website)

This repo is ready for Heroku web deploy (`Procfile`, `runtime.txt`, `requirements.txt` already included).

### 1) Create Instagram session file (required)

Run this locally on your machine:

```bash
instaloader --login YOUR_INSTAGRAM_LOGIN --no-pictures --no-videos --no-video-thumbnails --no-compress-json
```

After login, Instaloader creates:

- `session-YOUR_INSTAGRAM_LOGIN`

If Instagram asks for 2FA/challenge, complete it in terminal. When done, keep this session file safe.

### 2) Convert session file to base64 (single line)

Linux:

```bash
base64 -w 0 session-YOUR_INSTAGRAM_LOGIN > session.b64
```

macOS:

```bash
base64 session-YOUR_INSTAGRAM_LOGIN | tr -d '\n' > session.b64
```

Open `session.b64` and copy the full value.

### 3) Deploy from Heroku Dashboard (website only)

1. Go to Heroku Dashboard.
2. Click **New** → **Create new app**.
3. Enter app name and region, then click **Create app**.
4. Open the app and go to **Deploy** tab.
5. Under **Deployment method**, choose **GitHub**.
6. Connect your GitHub account and select this repository.
7. Choose branch (`main`) and click **Deploy Branch**.
8. Wait until build shows **Your app was successfully deployed**.

### 4) Set environment variables in Heroku Dashboard

1. Open app **Settings** tab.
2. Click **Reveal Config Vars**.
3. Add these keys:

- `INSTAGRAM_LOGIN_USER` = your Instagram username used to create session file
- `INSTAGRAM_SESSION_FILE_B64` = full content of `session.b64`
- `INSTAGRAM_SESSION_FILE` = `/tmp/instagram.session`

4. Save config vars.
5. Go to **More** → **Restart all dynos**.

### 5) Test deployed API

Use your app URL from Heroku settings:

```bash
curl -i https://YOUR-APP-NAME.herokuapp.com/api/pfp/instagram -o instagram_pfp.jpg
```

You should receive image bytes. Check headers:

- `X-Cache: MISS` on first call
- `X-Cache: HIT` on repeated calls (within 3 hours)

### 6) Refresh session when expired

If API starts returning auth errors:

1. Re-run Instaloader login to generate a fresh `session-YOUR_INSTAGRAM_LOGIN`.
2. Recreate `session.b64`.
3. Update `INSTAGRAM_SESSION_FILE_B64` in Heroku Config Vars.
4. Restart dynos from Heroku Dashboard.

## Notes

- Cache TTL is fixed at **3 hours** (`10800` seconds).
- Image files are cached on local disk (`/tmp/instagram-pfp-cache` by default).
- Cache metadata is in-memory per dyno process.
- A valid and fresh Instaloader session is required.
