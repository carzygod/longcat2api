# longcat2api Implementation Notes

## Current Principle

LongCat Web initializes Meituan H5guard with `fetchHook` and `xhrHook` for `longcat.chat`. Direct backend HTTP requests are therefore not the stable path. The service keeps a real Playwright browser context and lets the LongCat frontend perform the signed requests.

## Generation Flow

1. Keep a persistent browser profile in `LONGCAT_BROWSER_DATA`.
2. Login through `/admin?key=<LONGCAT_API_KEY>` by scanning the LongCat/Meituan QR screenshot, or import a full Cookie request header.
3. For normal text chat, open the LongCat home page, fill the editor, submit without selecting media mode, then collect assistant text from response payloads, session detail, and new DOM text.
4. For image generation, open the LongCat home page, fill the editor, select `图片生成`, submit, then collect result URLs.
5. For video generation, open the LongCat home page, fill the editor, select `视频生成`, submit, then collect result URLs from `task-check`, `session-detail`, and rendered DOM nodes.

## Verified Locators

| Purpose | Selector |
| --- | --- |
| Prompt editor | `.tiptap.ProseMirror[contenteditable='true']` |
| Image mode | text `图片生成` |
| Video mode | text `视频生成` |
| Send button | `.send-btn:not(.send-btn-disabled)` |

## Known Gaps

- Reference-image upload is not wired yet. It should be added after capturing a logged-in `/api/v1/appendix-upload` payload.
- `longcat-video-fast` currently maps to the same Web video generation switch because the public UI does not expose a stable named model switch in the captured state.
- Generation is serialized per browser profile to avoid conversation/result mixing.

## Admin Compatibility Layer

The Admin UI exposes the same operational shape as the existing gen2api Web-provider dashboards:

- `GET /admin/api/system`
- `GET /admin/api/accounts`
- `POST /admin/api/accounts/default/start`
- `POST /admin/api/accounts/default/stop`
- `POST /admin/api/accounts/default/restart`
- `POST /admin/api/accounts/default/probe`
- `GET /admin/api/accounts/default/cookies`
- `GET /admin/api/accounts/default/screenshot`
- `POST /admin/api/accounts/default/qr-login`
- `GET /admin/api/accounts/default/qr-login`
- `GET /admin/api/logs`
- `GET|PUT /admin/api/service/api-key`

LongCat currently uses one persistent browser profile. These endpoints therefore expose a single `default` account rather than a real multi-account scheduler. Do not add account-rotation claims until multiple independent LongCat profiles have been verified.
