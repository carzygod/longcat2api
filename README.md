# LONGCAT-WEB-01 / longcat2api

`longcat2api` is a Web reverse-proxy service for [LongCat](https://longcat.chat/). It does not use an official API key and does not call an official provider API. Instead, it keeps a real logged-in LongCat browser session with Playwright, performs generation through the LongCat Web UI, and exposes OpenAI-style image and video endpoints for NewAPI or other gateway systems.

The project is intended to be operated as `LONGCAT-WEB-01` in the gen2api provider family. Its Admin WebUI follows the same interaction pattern used by the existing gen2api Web reverse-proxy dashboards: dark control dashboard, account pool tab, one-click login/status actions, interface test tab, request logs, and system/API-key management.

## Current Scope

| Capability | Status | Notes |
| --- | --- | --- |
| LongCat Web login persistence | Supported | Playwright persistent profile + saved cookies |
| Cookie Header import | Supported | Paste raw `Cookie: name=value; ...` request header |
| QR login screenshot | Supported | Opens LongCat login flow and returns current browser screenshot |
| Text-to-image | Supported | Uses real Web UI flow and extracts generated media URL |
| Text-to-video | Supported | Uses real Web UI flow and extracts generated media URL |
| OpenAI-compatible model list | Supported | `/v1/models` |
| NewAPI basic reverse proxy | Supported | Use API Base `/v1`, Bearer token, and listed models |
| Multi-account rotation | Not implemented | Current version exposes one default persistent browser account |
| Reference image upload | Not implemented | Needs a captured, stable LongCat upload payload before wiring |
| Quota synchronization | Not implemented | LongCat Web has no stable public quota endpoint confirmed here |

## How It Works

LongCat Web enables frontend-side signing and browser state checks. Raw `httpx` requests cannot reliably reproduce the required browser context. For that reason `longcat2api` runs provider traffic from inside the browser page:

1. Start a persistent Chromium profile.
2. Load saved cookies from `LONGCAT_SESSION_FILE`.
3. Open `https://longcat.chat/`.
4. Verify login with LongCat Web user endpoints.
5. For generation, fill the visible prompt editor, switch to image or video mode, and submit from the Web UI.
6. Watch LongCat task/session responses and current DOM media elements.
7. Return only after image/video URLs are collected, or fail with a clear timeout/provider error.

Generation is serialized per browser profile. This avoids multiple simultaneous Web UI operations mixing conversations or returning a media URL from the wrong request.

## Models

| Type | Model name | Endpoint |
| --- | --- | --- |
| Image | `longcat-image` | `/v1/images/generations` |
| Video | `longcat-video` | `/v1/videos` |
| Video alias | `longcat-video-fast` | `/v1/videos` |
| Chat-compatible image wrapper | `longcat-image` | `/v1/chat/completions` |
| Chat-compatible video wrapper | `longcat-video` / `longcat-video-fast` | `/v1/chat/completions` |

`longcat-video-fast` is currently an alias exposed for gateway compatibility. The LongCat Web UI decides the actual model/quality available to the logged-in account.

## HTTP API

### Health

```http
GET /health
```

Returns service and browser readiness. This endpoint does not require the API key.

### Model List

```http
GET /v1/models
Authorization: Bearer <LONGCAT_API_KEY>
```

Example response:

```json
{
  "object": "list",
  "data": [
    {"id": "longcat-image", "object": "model", "created": 0, "owned_by": "longcat"},
    {"id": "longcat-video", "object": "model", "created": 0, "owned_by": "longcat"},
    {"id": "longcat-video-fast", "object": "model", "created": 0, "owned_by": "longcat"}
  ]
}
```

### Text-to-Image

```http
POST /v1/images/generations
Authorization: Bearer <LONGCAT_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "longcat-image",
  "prompt": "生成一只可爱的猫咪图片，柔和光线，高清细节。",
  "n": 1,
  "size": "1024x1024"
}
```

Response shape:

```json
{
  "created": 1780000000,
  "data": [
    {"url": "https://..."}
  ],
  "provider": "longcat",
  "raw": {
    "status": "succeeded",
    "kind": "image",
    "urls": ["https://..."]
  }
}
```

### Text-to-Video

```http
POST /v1/videos
Authorization: Bearer <LONGCAT_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "longcat-video",
  "prompt": "一个白色立方体在桌面上缓慢旋转，真实摄影风格，五秒短视频。",
  "wait": true
}
```

Aliases:

```text
POST /v1/video/generations
POST /v1/videos/generations
GET  /v1/videos/{task_id}
GET  /v1/video/generations/{task_id}
GET  /v1/videos/generations/{task_id}
```

When `wait` is `true`, the request blocks until the generated video URL is collected or `LONGCAT_VIDEO_TIMEOUT` is reached. When `wait` is `false`, the service creates an in-memory async task and the caller can poll by `task_id`.

### Chat-Compatible Wrapper

```http
POST /v1/chat/completions
Authorization: Bearer <LONGCAT_API_KEY>
Content-Type: application/json
```

```json
{
  "model": "longcat-image",
  "messages": [
    {"role": "user", "content": "生成一张赛博城市夜景图片"}
  ]
}
```

This wrapper is intentionally thin. It extracts user/system text and calls the image or video path according to the model name. It is useful for gateways that can only route chat-completion style requests.

## Admin WebUI

Open:

```text
http://<host>:<port>/admin?key=<LONGCAT_API_KEY>
```

Main tabs:

| Tab | Purpose |
| --- | --- |
| 账号池 | Shows the default LongCat browser account, browser state, login state, cookie count, page URL, and action buttons |
| 接口测试 | Sends real image/video generation requests through the same `/v1` endpoints used by NewAPI |
| 请求日志 | Shows recent service requests, status codes, latency, and unexpected errors |
| 系统 | Shows data paths, browser profile paths, timeout values, exposed models, and the runtime API key |

Important actions:

| Action | Behavior |
| --- | --- |
| 扫码登录 | Opens LongCat login flow and displays a browser screenshot for QR/login confirmation |
| 导入 Cookie | Parses a raw browser request cookie header and injects cookies into the Playwright profile |
| 测活 | Calls LongCat user/config endpoints from inside the browser context |
| Cookies | Displays sanitized cookie metadata; values are masked |
| 截图 | Captures the current browser page to confirm login, captcha, or provider UI state |
| 重启浏览器 | Restarts Playwright while keeping the persistent profile directory |

## NewAPI Channel Configuration

Recommended NewAPI channel fields:

| Field | Value |
| --- | --- |
| Channel type | OpenAI-compatible custom channel |
| Base URL | `http://<host>:<port>/v1` |
| API key | `<LONGCAT_API_KEY>` |
| Models | `longcat-image,longcat-video,longcat-video-fast` |
| Image endpoint | `/images/generations` |
| Video endpoint | Route according to NewAPI custom video support; direct service endpoint is `/videos` |

Before routing production traffic, use the Admin `接口测试` tab to confirm the logged-in LongCat account can generate media in the browser profile on that server.

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `LONGCAT_API_KEY` | `longcat-admin` | Bearer/query/admin key for this service |
| `LONGCAT_HOST` | `0.0.0.0` | Listen host |
| `LONGCAT_PORT` | `9090` | Listen port inside the process/container |
| `LONGCAT_DATA_DIR` | `/app/data` in Docker, `./data` otherwise | Root for profile/session files |
| `LONGCAT_BROWSER_DATA` | `<data>/browser` | Chromium persistent profile path |
| `LONGCAT_SESSION_FILE` | `<data>/longcat_session.json` | Saved cookie/session JSON |
| `LONGCAT_HEADLESS` | `true` | Set `false` only when running with a visible desktop |
| `LONGCAT_START_BROWSER` | `true` | Start browser during service boot |
| `LONGCAT_IMAGE_TIMEOUT` | `240` | Image generation wait timeout in seconds |
| `LONGCAT_VIDEO_TIMEOUT` | `900` | Video generation wait timeout in seconds |
| `LONGCAT_REQUEST_LOG_LIMIT` | `200` | In-memory Admin request log length |
| `LONGCAT_LOG_LEVEL` | `INFO` | Python logging level |
| `LONGCAT_TIMEZONE` | `Asia/Shanghai` | Browser timezone |
| `LONGCAT_USER_AGENT` | Chrome-like UA | Browser user agent override |
| `LONGCAT_CHROMIUM_EXECUTABLE_PATH` | unset | Use a specific Chrome/Chromium binary |
| `LONGCAT_CHROMIUM_CHANNEL` | unset | Use a Playwright browser channel, for example `chrome` |

## Docker Deployment

```bash
docker build -t longcat-web-01:latest .

docker run -d \
  --name longcat-web-01 \
  --restart unless-stopped \
  -p 19091:9090 \
  -v /opt/longcat2api-data:/app/data \
  -e LONGCAT_API_KEY='change-this-key' \
  -e LONGCAT_HOST=0.0.0.0 \
  -e LONGCAT_PORT=9090 \
  longcat-web-01:latest
```

Then open:

```text
http://<server-ip>:19091/admin?key=change-this-key
```

## Manual Python Run

Use this only for development or debugging:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
LONGCAT_API_KEY=change-this-key LONGCAT_HOST=0.0.0.0 LONGCAT_PORT=19091 python -m longcat2api
```

## Login Guide

### Option A: QR Login

1. Open `/admin?key=<LONGCAT_API_KEY>`.
2. Click `扫码登录`.
3. Scan or complete the LongCat login flow from the returned browser screenshot.
4. Wait for the Admin page to show `ready`.
5. Use `接口测试` to generate one image and one video.

### Option B: Cookie Header Import

1. Open `https://longcat.chat/` in a browser where the account is logged in.
2. Open DevTools Network.
3. Click any LongCat request under `longcat.chat`.
4. Copy the complete request `Cookie` header in this format:

   ```text
   name=value; name2=value2; name3=value3
   ```

5. Open Admin `导入 Cookie`.
6. Paste the raw cookie string and import.
7. Run `测活` and then use `接口测试`.

Do not paste cookies into public chats, public logs, GitHub issues, or screenshots. Cookies are equivalent to a browser login session.

## Troubleshooting

| Symptom | Likely Cause | What To Check |
| --- | --- | --- |
| `LongCat account is not logged in` | Browser profile has no valid LongCat session | Open Admin, scan QR or import cookies, then run `测活` |
| Generation times out | Web task is still pending, provider blocked the request, or DOM/API schema changed | Use Admin screenshot and request logs; raise `LONGCAT_VIDEO_TIMEOUT` for long video jobs |
| Browser cannot start in Docker | Missing Chromium deps or sandbox issue | Rebuild Dockerfile; it runs `playwright install --with-deps chromium` |
| Login works locally but not server-side | Provider risk control, region/IP/captcha, or stale cookies | Use server Admin screenshot to inspect actual page state |
| NewAPI returns 404 for video | Gateway does not route custom video endpoint correctly | Call `/v1/videos` directly first; then adapt NewAPI route configuration |
| Cookie import succeeds but status remains false | Missing LongCat/Meituan login cookies or expired session | Copy a full request cookie header from a logged-in LongCat page |

## Development Notes

Core files:

| File | Responsibility |
| --- | --- |
| `longcat2api/server.py` | FastAPI service, OpenAI-compatible endpoints, Admin API facade |
| `longcat2api/browser_client.py` | Playwright browser lifecycle, LongCat Web flow, login/cookie helpers |
| `longcat2api/media.py` | Media URL extraction and classification |
| `longcat2api/admin_ui.py` | Embedded Admin WebUI |
| `docs/implementation-notes.md` | Implementation details and known follow-up work |

Useful checks:

```bash
python -m compileall longcat2api
python -m longcat2api
```

Do not commit browser profiles, cookies, generated media, logs, or `.env` files.

## Security Notes

- Keep `LONGCAT_API_KEY` private.
- Run the service behind a trusted firewall or reverse proxy.
- Treat cookies and `longcat_session.json` as secrets.
- The Admin WebUI is protected by the same key but should still not be exposed to untrusted networks.
- The runtime API-key update currently changes the in-memory key. For deterministic restarts, update the deployment environment variable as well.

## Limitations And Roadmap

The current implementation is intentionally conservative:

- It exposes a single persistent browser account because LongCat login/captcha behavior has not yet been validated for a safe multi-profile scheduler.
- It does not claim quota synchronization because a stable LongCat quota endpoint has not been confirmed.
- It does not send reference images yet. That should be added only after capturing and validating the official LongCat Web upload request, including any H5guard/browser signing requirements.
- It returns generated media URLs collected from task/session payloads and the DOM. If LongCat changes its frontend schema, update `browser_client.py` selectors and payload extraction.
