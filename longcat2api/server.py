from __future__ import annotations

import asyncio
import logging
import os
import platform
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .admin_ui import ADMIN_HTML
from .browser_client import LongCatBrowserClient, data_root

log = logging.getLogger("longcat2api")


API_KEY = os.environ.get("LONGCAT_API_KEY", "longcat-admin")
HOST = os.environ.get("LONGCAT_HOST", "0.0.0.0")
PORT = int(os.environ.get("LONGCAT_PORT", "9090"))
IMAGE_TIMEOUT = int(os.environ.get("LONGCAT_IMAGE_TIMEOUT", "240"))
VIDEO_TIMEOUT = int(os.environ.get("LONGCAT_VIDEO_TIMEOUT", "900"))
CHAT_TIMEOUT = int(os.environ.get("LONGCAT_CHAT_TIMEOUT", "120"))
REQUEST_LOG_LIMIT = int(os.environ.get("LONGCAT_REQUEST_LOG_LIMIT", "200"))


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str = "longcat-image"
    n: int = 1
    size: str | None = "1024x1024"
    response_format: str | None = "url"
    image_url: Any | None = None
    input_image: Any | None = None
    reference_images: Any | None = None


class VideoGenerationRequest(BaseModel):
    prompt: str
    model: str = "longcat-video"
    wait: bool = True
    response_format: str | None = "url"
    duration: int | None = None
    size: str | None = None
    ratio: str | None = None
    image_url: Any | None = None
    input_image: Any | None = None
    reference_images: Any | None = None


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str = "longcat-chat"
    messages: list[ChatMessage]
    stream: bool = False


class CookieImportRequest(BaseModel):
    cookie_header: str


class ServiceKeyUpdate(BaseModel):
    api_key: str


class _Task:
    def __init__(self, *, task_id: str, kind: Literal["image", "video"], prompt: str, reference_images: list[str] | None = None) -> None:
        self.task_id = task_id
        self.kind = kind
        self.prompt = prompt
        self.reference_images = reference_images or []
        self.created = int(time.time())
        self.updated = self.created
        self.status = "queued"
        self.result: dict[str, Any] | None = None
        self.error = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.task_id,
            "object": "video.generation",
            "created": self.created,
            "updated": self.updated,
            "status": self.status,
            "prompt": self.prompt,
            "reference_images": self.reference_images,
            "result": self.result,
            "error": self.error or None,
        }


client = LongCatBrowserClient(
    headless=os.environ.get("LONGCAT_HEADLESS", "true").lower() != "false",
    user_data_dir=os.environ.get("LONGCAT_BROWSER_DATA"),
    session_file=os.environ.get("LONGCAT_SESSION_FILE"),
)
tasks: dict[str, _Task] = {}
request_logs: deque[dict[str, Any]] = deque(maxlen=REQUEST_LOG_LIMIT)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(
        level=os.environ.get("LONGCAT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    startup_task: asyncio.Task[None] | None = None
    if os.environ.get("LONGCAT_START_BROWSER", "true").lower() != "false":
        async def start_browser_background() -> None:
            try:
                await client.start()
            except Exception as exc:
                log.warning("LongCat browser did not start during boot: %s", exc)

        startup_task = asyncio.create_task(start_browser_background())
    yield
    if startup_task and not startup_task.done():
        startup_task.cancel()
    await client.stop()


app = FastAPI(title="longcat2api", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    error = ""
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        path = request.url.path
        if path != "/admin/api/logs":
            request_logs.appendleft(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "error": error,
                    "client": request.client.host if request.client else "",
                }
            )


def _current_api_key() -> str:
    return API_KEY


def _check_auth(request: Request) -> None:
    api_key = _current_api_key()
    if not api_key:
        return
    query_key = request.query_params.get("key")
    header = request.headers.get("authorization", "")
    bearer = header.removeprefix("Bearer ").strip() if header.lower().startswith("bearer ") else ""
    x_key = request.headers.get("x-api-key", "")
    if api_key not in {query_key, bearer, x_key}:
        raise HTTPException(status_code=401, detail="invalid api key")


def _models() -> list[dict[str, Any]]:
    return [
        {"id": "longcat-chat", "object": "model", "created": 0, "owned_by": "longcat"},
        {"id": "longcat-image", "object": "model", "created": 0, "owned_by": "longcat"},
        {"id": "longcat-video", "object": "model", "created": 0, "owned_by": "longcat"},
        {"id": "longcat-video-fast", "object": "model", "created": 0, "owned_by": "longcat"},
    ]


def _extract_reference_images(*values: Any) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            text = value.strip()
            if text and text not in seen:
                seen.add(text)
                refs.append(text)
            return
        if isinstance(value, dict):
            for key in ("url", "image_url", "input_image", "reference_image"):
                if key in value:
                    add(value.get(key))
            return
        if isinstance(value, list):
            for item in value:
                add(item)

    for item in values:
        add(item)
    return refs


def _prompt_and_references_from_messages(messages: list[ChatMessage]) -> tuple[str, list[str]]:
    parts: list[str] = []
    refs: list[str] = []
    for msg in messages:
        if msg.role not in {"user", "system"}:
            continue
        if isinstance(msg.content, str):
            parts.append(msg.content)
        elif isinstance(msg.content, list):
            for item in msg.content:
                if isinstance(item, dict) and item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text") or ""))
                elif isinstance(item, dict) and item.get("type") in {"image_url", "input_image"}:
                    refs.extend(_extract_reference_images(item.get("image_url"), item.get("input_image"), item.get("url")))
                else:
                    refs.extend(_extract_reference_images(item))
        elif isinstance(msg.content, dict):
            refs.extend(_extract_reference_images(msg.content))
    return "\n".join(part for part in parts if part).strip(), _extract_reference_images(refs)


def _image_response(urls: list[str], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "created": int(time.time()),
        "data": [{"url": url} for url in urls],
        "provider": "longcat",
        "raw": raw,
    }


def _video_response(urls: list[str], raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"video-{uuid.uuid4().hex[:12]}",
        "object": "video.generation",
        "created": int(time.time()),
        "status": "succeeded",
        "data": [{"url": url} for url in urls],
        "provider": "longcat",
        "raw": raw,
    }


async def _run_task(task: _Task) -> None:
    task.status = "in_progress"
    task.updated = int(time.time())
    try:
        result = await client.generate(
            kind=task.kind,
            prompt=task.prompt,
            timeout=VIDEO_TIMEOUT if task.kind == "video" else IMAGE_TIMEOUT,
            reference_images=task.reference_images,
        )
        task.result = _video_response(result["urls"], result) if task.kind == "video" else _image_response(result["urls"], result)
        task.status = "succeeded"
    except Exception as exc:
        task.error = str(exc)
        task.status = "failed"
    finally:
        task.updated = int(time.time())


async def _safe_login_status(*, start_if_needed: bool = True) -> dict[str, Any]:
    if not start_if_needed and not client.is_ready:
        return {"logged_in": False, "status": "browser_stopped"}
    try:
        return await client.login_status()
    except Exception as exc:
        return {"logged_in": False, "error": str(exc)}


async def _account_snapshot(*, start_if_needed: bool = True) -> dict[str, Any]:
    provider = await _safe_login_status(start_if_needed=start_if_needed)
    public_provider = _sanitize_provider_payload(provider)
    logged_in = bool(provider.get("logged_in"))
    runtime = {
        "hot": client.is_ready,
        "ready": bool(client.is_ready and logged_in),
        "page_url": client.page_url,
        "headless": client.headless,
        "login_status": public_provider,
    }
    return {
        "id": "default",
        "name": "LongCat 默认账号",
        "provider": "longcat",
        "enabled": True,
        "status": "ready" if runtime["ready"] else ("login_required" if runtime["hot"] else "stopped"),
        "session_file": client.session_file,
        "last_error": provider.get("error") or "",
        "runtime": runtime,
        "quota": {
            "image_24h_limit": None,
            "video_24h_limit": None,
        },
        "quota_status": {
            "image": {"remaining": None, "used": None, "limit": None, "note": "LongCat Web 未公开稳定配额接口"},
            "video": {"remaining": None, "used": None, "limit": None, "note": "LongCat Web 未公开稳定配额接口"},
        },
    }


def _require_default_account(account_id: str) -> None:
    if account_id != "default":
        raise HTTPException(status_code=404, detail="longcat2api currently exposes one default browser account")


def _system_payload() -> dict[str, Any]:
    return {
        "service": "LONGCAT-WEB-01",
        "name": "longcat2api",
        "listen": f"{HOST}:{PORT}",
        "data_root": data_root(),
        "browser_data": client.user_data_dir,
        "session_file": client.session_file,
        "headless": client.headless,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "request_log_limit": REQUEST_LOG_LIMIT,
        "chat_timeout": CHAT_TIMEOUT,
        "image_timeout": IMAGE_TIMEOUT,
        "video_timeout": VIDEO_TIMEOUT,
        "models": _models(),
    }


def _mask_secret(value: Any) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "***" if text else ""
    return f"{text[:4]}***{text[-4:]}"


def _mask_phone(value: Any) -> str:
    text = str(value or "")
    if len(text) < 7:
        return _mask_secret(text)
    return f"{text[:3]}****{text[-4:]}"


def _sanitize_provider_payload(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_provider_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        lowered = key.lower()
        if lowered in {"token", "token2", "mt_c_token", "passport_token_key", "isid", "oops"}:
            sanitized[key] = _mask_secret(item)
        elif lowered == "phone":
            sanitized[key] = _mask_phone(item)
        else:
            sanitized[key] = _sanitize_provider_payload(item)
    return sanitized


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "longcat2api", "data_root": data_root(), "browser_ready": client.is_ready}


@app.get("/v1/models")
async def models(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return {"object": "list", "data": _models()}


@app.post("/v1/images/generations")
async def images(request: Request, req: ImageGenerationRequest) -> dict[str, Any]:
    _check_auth(request)
    if req.model not in {"longcat-image", "longcat"}:
        raise HTTPException(status_code=400, detail=f"unsupported image model: {req.model}")
    reference_images = _extract_reference_images(req.image_url, req.input_image, req.reference_images)
    try:
        result = await client.generate(kind="image", prompt=req.prompt, timeout=IMAGE_TIMEOUT, reference_images=reference_images)
    except RuntimeError as exc:
        if "not logged in" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise
    result["requested_n"] = req.n
    return _image_response(result["urls"], result)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, req: ChatCompletionRequest) -> dict[str, Any]:
    _check_auth(request)
    prompt, reference_images = _prompt_and_references_from_messages(req.messages)
    if not prompt:
        raise HTTPException(status_code=400, detail="empty prompt")
    if "video" in req.model:
        try:
            result = await client.generate(kind="video", prompt=prompt, timeout=VIDEO_TIMEOUT, reference_images=reference_images)
        except RuntimeError as exc:
            if "not logged in" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise
        content = "\n".join(result["urls"])
    elif "image" in req.model:
        try:
            result = await client.generate(kind="image", prompt=prompt, timeout=IMAGE_TIMEOUT, reference_images=reference_images)
        except RuntimeError as exc:
            if "not logged in" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise
        content = "\n".join(result["urls"])
    elif req.model in {"longcat-chat", "longcat-text", "longcat"}:
        try:
            result = await client.generate(kind="chat", prompt=prompt, timeout=CHAT_TIMEOUT)
        except RuntimeError as exc:
            if "not logged in" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise
        content = result["text"]
    else:
        raise HTTPException(status_code=400, detail=f"unsupported chat model: {req.model}")
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    }


@app.post("/v1/videos")
@app.post("/v1/video/generations")
@app.post("/v1/videos/generations")
async def videos(request: Request, req: VideoGenerationRequest) -> dict[str, Any]:
    _check_auth(request)
    if req.model not in {"longcat-video", "longcat-video-fast", "longcat"}:
        raise HTTPException(status_code=400, detail=f"unsupported video model: {req.model}")
    reference_images = _extract_reference_images(req.image_url, req.input_image, req.reference_images)
    if req.wait:
        try:
            result = await client.generate(kind="video", prompt=req.prompt, timeout=VIDEO_TIMEOUT, reference_images=reference_images)
        except RuntimeError as exc:
            if "not logged in" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise
        return _video_response(result["urls"], result)
    task_id = f"longcat-video-{uuid.uuid4().hex}"
    task = _Task(task_id=task_id, kind="video", prompt=req.prompt, reference_images=reference_images)
    tasks[task_id] = task
    asyncio.create_task(_run_task(task))
    return task.to_dict()


@app.get("/v1/videos/{task_id}")
@app.get("/v1/video/generations/{task_id}")
@app.get("/v1/videos/generations/{task_id}")
async def get_video_task(request: Request, task_id: str) -> dict[str, Any]:
    _check_auth(request)
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task.to_dict()


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request) -> str:
    _check_auth(request)
    return ADMIN_HTML.replace("__API_KEY__", _current_api_key())


@app.get("/admin/api/status")
async def admin_status(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return {
        "service": "longcat2api",
        "browser_ready": client.is_ready,
        "provider": _sanitize_provider_payload(await _safe_login_status()),
        "models": _models(),
    }


@app.get("/admin/api/system")
async def admin_system(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return _system_payload()


@app.get("/admin/api/accounts")
async def admin_accounts(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return {"accounts": [await _account_snapshot()], "default_account_id": "default"}


@app.post("/admin/api/accounts")
async def admin_create_account(request: Request) -> dict[str, Any]:
    _check_auth(request)
    raise HTTPException(status_code=409, detail="longcat2api currently uses a single persistent default browser account")


@app.delete("/admin/api/accounts/{account_id}")
async def admin_delete_account(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    raise HTTPException(status_code=409, detail="default LongCat browser account cannot be deleted")


@app.post("/admin/api/accounts/{account_id}/start")
async def admin_account_start(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    await client.start()
    return {"ok": True, "account": await _account_snapshot()}


@app.post("/admin/api/accounts/{account_id}/stop")
async def admin_account_stop(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    await client.stop()
    return {"ok": True, "account": await _account_snapshot(start_if_needed=False)}


@app.post("/admin/api/accounts/{account_id}/restart")
async def admin_account_restart(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    await client.restart()
    return {"ok": True, "account": await _account_snapshot()}


@app.post("/admin/api/accounts/{account_id}/probe")
async def admin_account_probe(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    status = await _safe_login_status()
    if not status.get("logged_in"):
        return {"ok": False, "status": "login_required", "login_status": _sanitize_provider_payload(status)}
    try:
        config = await client.provider_config()
    except Exception as exc:
        return {
            "ok": False,
            "status": "provider_error",
            "login_status": _sanitize_provider_payload(status),
            "error": str(exc),
        }
    return {
        "ok": True,
        "status": "ready",
        "login_status": _sanitize_provider_payload(status),
        "provider_config": _sanitize_provider_payload(config),
    }


@app.get("/admin/api/accounts/{account_id}/cookies")
async def admin_account_cookies(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    cookies = await client.cookies()
    sanitized = [
        {
            "name": cookie.get("name"),
            "domain": cookie.get("domain"),
            "path": cookie.get("path"),
            "expires": cookie.get("expires"),
            "httpOnly": cookie.get("httpOnly"),
            "secure": cookie.get("secure"),
            "sameSite": cookie.get("sameSite"),
            "value_preview": (cookie.get("value") or "")[:8] + "***",
        }
        for cookie in cookies
    ]
    return {"account_id": account_id, "total": len(cookies), "cookies": sanitized}


@app.get("/admin/api/accounts/{account_id}/screenshot")
async def admin_account_screenshot(request: Request, account_id: str) -> Response:
    _check_auth(request)
    _require_default_account(account_id)
    return Response(content=await client.screenshot(), media_type="image/png")


@app.post("/admin/api/accounts/{account_id}/qr-login")
async def admin_account_qr_start(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    data = await client.open_login_qr()
    logged_in = bool((data.get("status") or {}).get("logged_in"))
    login_status = _sanitize_provider_payload(data.get("status"))
    return {
        "account_id": account_id,
        "image_base64": data.get("image_base64"),
        "page_url": data.get("page_url"),
        "status": "confirmed" if logged_in else "waiting",
        "text": "已登录" if logged_in else "等待扫码确认",
        "login_status": login_status,
    }


@app.get("/admin/api/accounts/{account_id}/qr-login")
async def admin_account_qr_poll(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    status = await _safe_login_status()
    logged_in = bool(status.get("logged_in"))
    return {
        "account_id": account_id,
        "status": "confirmed" if logged_in else "waiting",
        "text": "已登录" if logged_in else "等待扫码确认",
        "login_status": _sanitize_provider_payload(status),
    }


@app.post("/admin/api/accounts/{account_id}/quota/sync")
async def admin_quota_sync(request: Request, account_id: str) -> dict[str, Any]:
    _check_auth(request)
    _require_default_account(account_id)
    return {
        "ok": False,
        "status": "not_supported",
        "message": "LongCat Web 当前没有稳定公开的图片/视频剩余额度接口，配额以实际生成结果为准。",
    }


@app.get("/admin/api/service/api-key")
async def admin_service_key(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return {"api_key": _current_api_key()}


@app.put("/admin/api/service/api-key")
async def admin_service_key_update(request: Request, req: ServiceKeyUpdate) -> dict[str, Any]:
    _check_auth(request)
    global API_KEY
    next_key = req.api_key.strip()
    if not next_key:
        raise HTTPException(status_code=400, detail="api_key cannot be empty")
    API_KEY = next_key
    return {"api_key": API_KEY}


@app.get("/admin/api/logs")
async def admin_logs(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return {"logs": list(request_logs)}


@app.post("/admin/api/login/qr")
async def admin_login_qr(request: Request) -> dict[str, Any]:
    _check_auth(request)
    return await client.open_login_qr()


@app.post("/admin/api/cookies")
async def admin_import_cookies(request: Request, req: CookieImportRequest) -> dict[str, Any]:
    _check_auth(request)
    count = await client.import_cookie_header(req.cookie_header)
    return {"imported": count, "status": _sanitize_provider_payload(await _safe_login_status())}


@app.post("/admin/api/restart")
async def admin_restart(request: Request) -> dict[str, Any]:
    _check_auth(request)
    await client.restart()
    return {"ok": True, "status": _sanitize_provider_payload(await _safe_login_status())}


@app.exception_handler(Exception)
async def exception_handler(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc)})
