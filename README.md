# Instagram-API

Render-deployable Instagram profile picture API built with Flask + Instaloader.

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

## Render deployment (manual via website)

This repo is ready for Render Web Service deployment.

Optional: this repo also includes `render.yaml`, so you can deploy with Render Blueprint if you prefer.

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

Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("session-YOUR_INSTAGRAM_LOGIN")) | Out-File -NoNewline session.b64
```

### 3) Deploy from Render Dashboard (website only)

1. Go to Render Dashboard.
2. Click **New** → **Web Service**.
3. Connect your GitHub account and select this repository.
4. Configure service:
	- **Environment**: `Python 3`
	- **Instance Type**: `Free`
	- **Build Command**: `pip install -r requirements.txt`
	- **Start Command**: `gunicorn app:app --workers 2 --threads 4 --timeout 120`
5. Click **Create Web Service** and wait for the first deploy to finish.

### 4) Set environment variables in Render Dashboard

1. Open your Render service.
2. Go to **Environment**.
3. Add these keys:

- `INSTAGRAM_LOGIN_USER` = your Instagram username used to create session file
- `INSTAGRAM_SESSION_FILE_B64` = full content of `session.b64`
- `INSTAGRAM_SESSION_FILE` = `/tmp/instagram.session`
- `IMAGE_CACHE_DIR` = `/tmp/instagram-pfp-cache`

4. Save changes.
5. Click **Manual Deploy** → **Deploy latest commit** (or restart service).

### 5) Test deployed API

Use your Render service URL:

```bash
curl -i https://YOUR-SERVICE-NAME.onrender.com/api/pfp/instagram -o instagram_pfp.jpg
```

You should receive image bytes. Check headers:

- `X-Cache: MISS` on first call
- `X-Cache: HIT` on repeated calls (within 3 hours)

### 6) Refresh session when expired

If API starts returning auth errors:

1. Re-run Instaloader login to generate a fresh `session-YOUR_INSTAGRAM_LOGIN`.
2. Recreate `session.b64`.
3. Update `INSTAGRAM_SESSION_FILE_B64` in Render Environment.
4. Redeploy/restart service from Render Dashboard.

## Notes

- Cache TTL is fixed at **3 hours** (`10800` seconds).
- Image files are cached on local disk (`/tmp/instagram-pfp-cache` by default).
- Cache metadata is in-memory per running Render service instance.
- A valid and fresh Instaloader session is required.

## Troubleshooting

### Free plan cold starts (Render)

- First request after idle time can be slow on free instances.
- This is expected behavior on Render free web services.
- Send one warm-up request to `/health` before high traffic if needed.

### 401/403 or auth-related failures

- Usually means the Instagram session is expired, challenged, or invalid.
- Recreate `session-YOUR_INSTAGRAM_LOGIN` locally using Instaloader login.
- Re-encode to `session.b64`, update `INSTAGRAM_SESSION_FILE_B64`, and redeploy.

### 404 from `/api/pfp/<username>`

- Username does not exist or is invalid.
- Verify the exact Instagram handle and retry.

### 500 from `/api/pfp/<username>`

Common causes:

- Missing config vars (`INSTAGRAM_LOGIN_USER`, `INSTAGRAM_SESSION_FILE_B64`, `INSTAGRAM_SESSION_FILE`)
- Corrupted/partial base64 value in `INSTAGRAM_SESSION_FILE_B64`
- Temporary Instagram/network block or connection failure

Fix checklist:

1. Confirm all env vars in Render Dashboard.
2. Recopy full base64 value (single line, no truncation).
3. Redeploy service and test `/health` first.

### Cache behavior questions

- `X-Cache: MISS` = fetched from Instagram and saved locally.
- `X-Cache: HIT` = served from local cached file.
- Cache is per running instance and expires after 3 hours.
