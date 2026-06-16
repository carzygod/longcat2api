# DOUBAO-WEB-01 / doubao2api

DOUBAO-WEB-01 is the maintained Doubao Web reverse-proxy provider used by the
gen2api stack.

Repository:

```text
https://github.com/carzygod/doubao2api
```

This service does not use official Volcengine/ARK API keys. It drives logged-in
Doubao Web sessions through Playwright and exposes OpenAI-compatible APIs for
chat, image generation, music generation, and async video generation.

## Capabilities

| Area | Status |
|---|---|
| Storage | SQLite |
| Redis | Not used |
| Admin WebUI | `/admin?key=<DOUBAO_API_KEY>` |
| Account pool | Multiple Doubao Web accounts |
| Login | Browser QR/login flow through Admin WebUI |
| Hot accounts | Keeps a configurable number of Playwright accounts warm |
| Account test | Sends a real chat request and requires model output |
| Chat API | OpenAI-compatible `/v1/chat/completions` |
| Image API | OpenAI-compatible `/v1/images/generations` |
| Music API | `/v1/audio/generations` |
| Video API | OpenAI-compatible `/v1/videos` plus legacy aliases |
| Video polling | `/v1/videos/{task_id}` plus legacy aliases |
| Video cancel | Local cancel on `/v1/videos/{task_id}/cancel` plus legacy aliases |
| Quota accounting | Local 24h image/video reservation and completion accounting |
| Quota retry | Video quota failures mark the account unavailable and can try the next account |
| NewAPI use | Can be added as an OpenAI-compatible channel for chat/image/video |

## Models

| Capability | Model |
|---|---|
| Chat | `doubao` |
| Chat | `doubao-pro` |
| Chat | `doubao-think` |
| Chat | `doubao-expert` |
| Image | `doubao-image` |
| Music | `doubao-music` |
| Video | `doubao-video` |
| Video alias | `seedance_v2.0` |
| Video alias | `seedance2.0` |
| Video alias | `seedance2.0fast` |
| Video alias | `seedance-2.0-fast` |
| Video alias | `seedance_2.0_fast` |
| Video alias | `seedance_v2.0_fast` |
| Video alias | `Seedance 2.0` |
| Video alias | `Seedance 2.0 Fast` |

The video aliases currently map to the observed Doubao Web Seedance 2.0 video
route. The public model recommended for NewAPI is `doubao-video`.

## Quick Start

Docker:

```bash
docker build -t doubao-web-01:latest .
docker run -d --name doubao-web-01 \
  -p 19090:9090 \
  -e DOUBAO_HOST=0.0.0.0 \
  -e DOUBAO_PORT=9090 \
  -e DOUBAO_API_KEY=change-me-api-key \
  -e DOUBAO_ACCOUNT_DATA_DIR=/app/data \
  -e DOUBAO_BROWSER_DATA=/app/data/browser \
  -e DOUBAO_SESSION_FILE=/app/data/.doubao_session.json \
  -v "$PWD/data:/app/data" \
  doubao-web-01:latest
```

Local:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
DOUBAO_API_KEY=change-me-api-key python -m doubao2api
```

Open the Admin WebUI:

```text
http://127.0.0.1:19090/admin?key=change-me-api-key
```

## Environment

| Variable | Default | Description |
|---|---|---|
| `DOUBAO_HOST` | `0.0.0.0` | Listen host |
| `DOUBAO_PORT` | `9090` | Listen port |
| `DOUBAO_API_KEY` | empty | Bearer token and Admin key |
| `DOUBAO_ACCOUNT_DATA_DIR` | `/app/data` | Account DB and account profiles |
| `DOUBAO_BROWSER_DATA` | `/app/data/browser` | Playwright browser profile root |
| `DOUBAO_SESSION_FILE` | `/app/data/.doubao_session.json` | Legacy single-session file |
| `DOUBAO_MAX_HOT_ACCOUNTS` | `2` | Max warm browser accounts |
| `DOUBAO_IMAGE_24H_QUOTA` | `30` | Default local 24h image quota per account |
| `DOUBAO_VIDEO_24H_QUOTA` | `10` | Default local 24h video quota units per account |
| `DOUBAO_QUOTA_WINDOW_SECONDS` | `86400` | Rolling quota accounting window |
| `DOUBAO_PC_VERSION` | `3.22.5` | Doubao Web client version hint |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` | empty | Optional system Chromium path |

## Account Management

1. Open `/admin?key=<DOUBAO_API_KEY>`.
2. Create an account with a readable name.
3. Start or restart the account browser.
4. Trigger QR/login.
5. Scan and confirm the account reaches a logged-in Doubao page.
6. Run account probe/test before routing production requests.

Deleting or disabling an account stops the corresponding browser client so stale
Chromium processes do not accumulate.

## Public APIs

All `/v1/*` APIs use:

```text
Authorization: Bearer <DOUBAO_API_KEY>
```

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Runtime health |
| `GET` | `/v1/models` | Model list |
| `POST` | `/v1/chat/completions` | OpenAI-compatible chat |
| `POST` | `/v1/images/generations` | OpenAI-compatible image generation |
| `POST` | `/v1/audio/generations` | Music generation |
| `POST` | `/v1/videos` | OpenAI-compatible async video creation |
| `GET` | `/v1/videos/{task_id}` | OpenAI-compatible video polling |
| `POST` | `/v1/videos/{task_id}/cancel` | OpenAI-compatible local cancel |
| `POST` | `/v1/video/generations` | Legacy async video creation |
| `GET` | `/v1/video/generations/{task_id}` | Legacy video polling |
| `POST` | `/v1/video/generations/{task_id}/cancel` | Legacy local cancel |
| `POST` | `/v1/videos/generations` | Legacy plural alias |
| `GET` | `/v1/videos/generations/{task_id}` | Legacy plural polling |
| `POST` | `/v1/videos/generations/{task_id}/cancel` | Legacy plural cancel |
| `POST` | `/v1/files` | Upload file |
| `GET` | `/v1/files/download` | Resolve uploaded file download URL |
| `POST` | `/v1/images/upload` | Upload image for multimodal use |

## Admin APIs

Admin requests use `X-Admin-Key: <DOUBAO_API_KEY>` or `/admin?key=<DOUBAO_API_KEY>`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/api/system` | Runtime, model, quota, and account summary |
| `GET` | `/admin/api/accounts` | List accounts |
| `POST` | `/admin/api/accounts` | Create account |
| `PATCH` | `/admin/api/accounts/{account_id}` | Update account metadata |
| `DELETE` | `/admin/api/accounts/{account_id}` | Delete account and stop browser |
| `POST` | `/admin/api/accounts/{account_id}/start` | Start account browser |
| `POST` | `/admin/api/accounts/{account_id}/stop` | Stop account browser |
| `POST` | `/admin/api/accounts/{account_id}/restart` | Restart account browser |
| `POST` | `/admin/api/accounts/{account_id}/probe` | Real chat probe |
| `POST` | `/admin/api/accounts/{account_id}/quota/sync` | Sync provider quota when detectable |
| `GET` | `/admin/api/accounts/{account_id}/screenshot` | Browser screenshot |
| `POST` | `/admin/api/accounts/{account_id}/qr-login` | Start QR login |
| `GET` | `/admin/api/accounts/{account_id}/qr-login` | Poll QR login state |

## Examples

Chat:

```bash
curl http://127.0.0.1:19090/v1/chat/completions \
  -H "Authorization: Bearer change-me-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao",
    "messages": [{"role": "user", "content": "Reply with OK only."}],
    "stream": false
  }'
```

Image:

```bash
curl http://127.0.0.1:19090/v1/images/generations \
  -H "Authorization: Bearer change-me-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-image",
    "prompt": "a white cube on a desk, realistic photo style",
    "n": 1,
    "size": "1:1"
  }'
```

OpenAI-compatible video:

```bash
curl http://127.0.0.1:19090/v1/videos \
  -H "Authorization: Bearer change-me-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-video",
    "prompt": "a white cube slowly rotating on a desk, realistic photo style",
    "duration": 5,
    "resolution": "720P",
    "ratio": "16:9"
  }'
```

Poll:

```bash
curl http://127.0.0.1:19090/v1/videos/<task_id> \
  -H "Authorization: Bearer change-me-api-key"
```

Quota exhaustion is returned as a provider error, for example:

```json
{
  "status": "failed",
  "error": {
    "type": "provider_quota_exhausted",
    "code": "quota_exhausted",
    "message": "provider quota exhausted"
  }
}
```
