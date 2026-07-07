from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from .media import classify_media_urls

log = logging.getLogger(__name__)

LONGCAT_URL = "https://longcat.chat"
DEFAULT_TIMEZONE = os.environ.get("LONGCAT_TIMEZONE", "Asia/Shanghai")
DEFAULT_USER_AGENT = os.environ.get(
    "LONGCAT_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
)
DEFAULT_CHROMIUM_EXECUTABLE_PATH = (
    os.environ.get("LONGCAT_CHROMIUM_EXECUTABLE_PATH")
    or os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
)
DEFAULT_CHROMIUM_CHANNEL = os.environ.get("LONGCAT_CHROMIUM_CHANNEL", "").strip()


class LongCatBrowserClient:
    """Persistent LongCat Web session.

    LongCat enables Meituan H5guard fetch/xhr signing on the page. For that
    reason all provider calls are executed in the browser page instead of raw
    httpx requests.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        user_data_dir: str | None = None,
        session_file: str | None = None,
    ) -> None:
        root = data_root()
        self.headless = headless
        self.user_data_dir = user_data_dir or os.path.join(root, "browser")
        self.session_file = session_file or os.path.join(root, "longcat_session.json")
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._ready = False
        self._lock = asyncio.Lock()
        self._last_responses: list[dict[str, Any]] = []

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def page_url(self) -> str:
        return self._page.url if self._page else ""

    async def start(self) -> None:
        if self._page and self._context:
            return
        Path(self.user_data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.session_file).parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale_profile_locks()
        self._playwright = await async_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
        ]
        launch_options: dict[str, Any] = {
            "headless": self.headless,
            "args": launch_args,
        }
        if DEFAULT_CHROMIUM_EXECUTABLE_PATH:
            launch_options["executable_path"] = DEFAULT_CHROMIUM_EXECUTABLE_PATH
        if DEFAULT_CHROMIUM_CHANNEL and not DEFAULT_CHROMIUM_EXECUTABLE_PATH:
            launch_options["channel"] = DEFAULT_CHROMIUM_CHANNEL
        try:
            self._context = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                **launch_options,
                viewport={"width": 1365, "height": 900},
                locale="zh-CN",
                timezone_id=DEFAULT_TIMEZONE,
                user_agent=DEFAULT_USER_AGENT,
            )
        except Exception as exc:
            if DEFAULT_CHROMIUM_EXECUTABLE_PATH or DEFAULT_CHROMIUM_CHANNEL or "Executable doesn't exist" not in str(exc):
                raise
            log.warning("Bundled Playwright Chromium is missing, retrying with system Chrome channel")
            launch_options["channel"] = "chrome"
            self._context = await self._playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                **launch_options,
                viewport={"width": 1365, "height": 900},
                locale="zh-CN",
                timezone_id=DEFAULT_TIMEZONE,
                user_agent=DEFAULT_USER_AGENT,
            )
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        await Stealth(navigator_languages_override=("zh-CN", "zh")).apply_stealth_async(self._page)
        self._page.on("response", lambda response: asyncio.create_task(self._record_response(response)))
        await self._load_saved_cookies()
        await self.goto_home()
        self._ready = True

    async def stop(self) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._context = None
        self._page = None
        self._playwright = None
        self._ready = False

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def goto_home(self) -> None:
        page = await self.require_page()
        if not page.url.startswith(LONGCAT_URL):
            await page.goto(LONGCAT_URL, wait_until="domcontentloaded", timeout=60_000)
        else:
            await page.goto(LONGCAT_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(2000)

    async def require_page(self) -> Page:
        if not self._page:
            await self.start()
        if not self._page:
            raise RuntimeError("LongCat browser page is not available")
        return self._page

    async def login_status(self) -> dict[str, Any]:
        await self.start()
        current = await self.browser_json("GET", f"/api/v1/user-current?t={int(time.time() * 1000)}")
        login = await self.browser_json("GET", "/api/v1/login-info")
        data = {
            "logged_in": bool(((current.get("data") or {}).get("loginStatus") == 1) or ((login.get("data") or {}).get("loginInfo") == 1)),
            "user_current": current,
            "login_info": login,
        }
        if data["logged_in"]:
            await self.save_cookies()
        return data

    async def provider_config(self) -> dict[str, Any]:
        return await self.browser_json("GET", "/api/v1/configList")

    async def open_login_qr(self) -> dict[str, Any]:
        await self.start()
        page = await self.require_page()
        await self.goto_home()
        for selector in [
            "text=请先登录",
            ".slider-footer-content",
            "text=图片生成",
        ]:
            try:
                await page.locator(selector).first.click(timeout=3000)
                break
            except Exception:
                continue
        await page.wait_for_timeout(3000)
        png = await page.screenshot(full_page=True)
        return {
            "image_base64": base64.b64encode(png).decode("ascii"),
            "page_url": page.url,
            "status": await self.login_status(),
        }

    async def import_cookie_header(self, cookie_header: str) -> int:
        await self.start()
        cookies = []
        for part in cookie_header.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            value = value.strip()
            if not name:
                continue
            cookies.append({"name": name, "value": value, "domain": ".longcat.chat", "path": "/"})
        if not cookies:
            return 0
        context = await self.require_context()
        await context.add_cookies(cookies)
        await self.save_cookies()
        await self.goto_home()
        return len(cookies)

    async def cookies(self) -> list[dict[str, Any]]:
        context = await self.require_context()
        return await context.cookies([LONGCAT_URL, "https://passport.meituan.com"])

    async def screenshot(self) -> bytes:
        page = await self.require_page()
        return await page.screenshot(full_page=True)

    async def save_cookies(self) -> None:
        context = await self.require_context()
        cookies = await context.cookies([LONGCAT_URL, "https://passport.meituan.com"])
        Path(self.session_file).write_text(json.dumps({"cookies": cookies}, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _load_saved_cookies(self) -> None:
        path = Path(self.session_file)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cookies = payload.get("cookies") if isinstance(payload, dict) else payload
            if cookies:
                context = await self.require_context()
                await context.add_cookies(cookies)
                log.info("Loaded %d LongCat cookies", len(cookies))
        except Exception as exc:
            log.warning("Failed to load LongCat cookies from %s: %s", path, exc)

    async def require_context(self) -> BrowserContext:
        if not self._context:
            await self.start()
        if not self._context:
            raise RuntimeError("LongCat browser context is not available")
        return self._context

    async def browser_json(self, method: str, path: str, body: Any | None = None, timeout_ms: int = 60_000) -> dict[str, Any]:
        result = await self.browser_fetch(method, path, body=body, timeout_ms=timeout_ms)
        text = result.get("text") or ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LongCat returned non-JSON response for {path}: {text[:300]}") from exc
        if result.get("status", 0) >= 400:
            raise RuntimeError(f"LongCat HTTP {result.get('status')}: {parsed}")
        return parsed

    async def browser_fetch(self, method: str, path: str, body: Any | None = None, timeout_ms: int = 60_000) -> dict[str, Any]:
        await self.start()
        page = await self._longcat_fetch_page()
        close_after = page is not self._page
        try:
            return await page.evaluate(
                """async ({method, path, body, timeoutMs}) => {
              const controller = new AbortController();
              const timer = setTimeout(() => controller.abort(), timeoutMs);
              try {
                const url = path.startsWith('http') ? path : new URL(path, 'https://longcat.chat').toString();
                const headers = {
                  'Accept': 'application/json, text/plain, */*',
                  'X-Requested-With': 'XMLHttpRequest',
                  'X-Client-Language': localStorage.getItem('locale') || 'zh-CN'
                };
                const init = {method, headers, credentials: 'include', signal: controller.signal};
                if (body !== undefined && body !== null) {
                  headers['Content-Type'] = 'application/json';
                  init.body = JSON.stringify(body);
                }
                const res = await fetch(url, init);
                const text = await res.text();
                return {status: res.status, url: res.url, text};
              } finally {
                clearTimeout(timer);
              }
            }""",
                {"method": method.upper(), "path": path, "body": body, "timeoutMs": timeout_ms},
            )
        finally:
            if close_after:
                try:
                    await page.close()
                except Exception:
                    pass

    async def _longcat_fetch_page(self) -> Page:
        page = await self.require_page()
        if page.url.startswith(LONGCAT_URL):
            return page
        context = await self.require_context()
        fetch_page = await context.new_page()
        try:
            await Stealth(navigator_languages_override=("zh-CN", "zh")).apply_stealth_async(fetch_page)
        except Exception:
            pass
        await fetch_page.goto(LONGCAT_URL, wait_until="domcontentloaded", timeout=60_000)
        await fetch_page.wait_for_timeout(2000)
        return fetch_page

    async def generate(
        self,
        *,
        kind: Literal["chat", "image", "video"],
        prompt: str,
        timeout: int,
    ) -> dict[str, Any]:
        async with self._lock:
            status = await self.login_status()
            if not status["logged_in"]:
                raise RuntimeError("LongCat account is not logged in. Open /admin and scan the login QR first.")
            self._last_responses.clear()
            page = await self.require_page()
            await self.goto_home()
            baseline_texts = await self._dom_text_candidates()
            await self._fill_prompt(prompt)
            if kind == "chat":
                await self._prepare_plain_chat()
            else:
                await self._select_mode(kind)
            await self._click_send()
            if kind == "chat":
                result = await self._wait_for_chat(prompt=prompt, baseline_texts=baseline_texts, timeout=timeout)
            else:
                result = await self._wait_for_media(kind=kind, timeout=timeout)
            await self.save_cookies()
            return result

    async def _fill_prompt(self, prompt: str) -> None:
        page = await self.require_page()
        editor = page.locator(".tiptap.ProseMirror[contenteditable='true']").first
        await editor.wait_for(state="visible", timeout=30_000)
        await editor.click()
        try:
            await editor.fill("")
        except Exception:
            modifier = "Meta" if os.name == "posix" else "Control"
            await page.keyboard.press(f"{modifier}+A")
            await page.keyboard.press("Backspace")
        await editor.fill(prompt)
        await page.wait_for_timeout(500)

    async def _select_mode(self, kind: str) -> None:
        page = await self.require_page()
        label = "图片生成" if kind == "image" else "视频生成"
        await page.get_by_text(label, exact=True).click(timeout=10_000)
        await page.wait_for_timeout(500)

    async def _prepare_plain_chat(self) -> None:
        page = await self.require_page()
        await page.evaluate(
            """(labels) => {
              function rgbParts(value) {
                const match = String(value || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                return match ? match.slice(1, 4).map(Number) : [];
              }
              function isGreen(value) {
                const [r, g, b] = rgbParts(value);
                return g > 120 && g > r + 25 && g > b + 25;
              }
              for (const label of labels) {
                const nodes = [...document.querySelectorAll('button,[role="button"],div,span')]
                  .filter(el => (el.innerText || el.textContent || '').trim() === label);
                const visible = nodes.find(el => {
                  const rect = el.getBoundingClientRect();
                  return rect.width > 0 && rect.height > 0;
                });
                if (!visible) continue;
                const target = visible.closest('button,[role="button"]') || visible;
                const html = target.outerHTML.slice(0, 500).toLowerCase();
                const style = getComputedStyle(target);
                const active =
                  /active|selected|checked|is-on|true/.test(html) ||
                  isGreen(style.color) ||
                  isGreen(style.borderColor) ||
                  isGreen(style.backgroundColor);
                if (active) target.click();
              }
            }""",
            ["联网搜索", "深度思考", "深度研究"],
        )
        await page.wait_for_timeout(500)

    async def _click_send(self) -> None:
        page = await self.require_page()
        send = page.locator(".send-btn:not(.send-btn-disabled)").first
        try:
            await send.wait_for(state="visible", timeout=10_000)
            await send.click(timeout=10_000)
        except Exception:
            await page.keyboard.press("Enter")
        await page.wait_for_timeout(1500)

    async def _wait_for_media(self, *, kind: str, timeout: int) -> dict[str, Any]:
        page = await self.require_page()
        deadline = time.monotonic() + timeout
        last_snapshot: dict[str, Any] = {}
        while time.monotonic() < deadline:
            await page.wait_for_timeout(3000)
            snapshot = await self._collect_result_snapshot(kind)
            last_snapshot = snapshot
            if snapshot["urls"]:
                return {
                    "status": "succeeded",
                    "kind": kind,
                    "urls": snapshot["urls"],
                    "conversation_id": snapshot.get("conversation_id", ""),
                    "raw": snapshot,
                }
            if snapshot.get("terminal_error"):
                raise RuntimeError(snapshot["terminal_error"])
        raise TimeoutError(f"Timed out waiting for LongCat {kind} result. Last snapshot: {last_snapshot}")

    async def _wait_for_chat(self, *, prompt: str, baseline_texts: list[str], timeout: int) -> dict[str, Any]:
        page = await self.require_page()
        deadline = time.monotonic() + timeout
        baseline = {self._normalize_text(text) for text in baseline_texts}
        last_snapshot: dict[str, Any] = {}
        while time.monotonic() < deadline:
            await page.wait_for_timeout(2000)
            snapshot = await self._collect_chat_snapshot(prompt=prompt, baseline=baseline)
            last_snapshot = snapshot
            text = snapshot.get("text") or ""
            if text:
                return {
                    "status": "succeeded",
                    "kind": "chat",
                    "text": text,
                    "conversation_id": snapshot.get("conversation_id", ""),
                    "raw": snapshot,
                }
            if snapshot.get("terminal_error"):
                raise RuntimeError(snapshot["terminal_error"])
        raise TimeoutError(f"Timed out waiting for LongCat chat result. Last snapshot: {last_snapshot}")

    async def _collect_chat_snapshot(self, *, prompt: str, baseline: set[str]) -> dict[str, Any]:
        page = await self.require_page()
        conversation_id = self._conversation_id_from_url(page.url)
        payloads = list(self._last_responses[-40:])
        if conversation_id:
            try:
                detail = await self.browser_json("GET", f"/api/v1/session-detail?conversationId={conversation_id}")
                payloads.append({"url": "session-detail", "body": detail})
            except Exception as exc:
                payloads.append({"url": "session-detail", "error": str(exc)})
        payload_texts = self._payload_text_candidates(payloads)
        dom_texts = await self._dom_text_candidates()
        candidates = self._filter_chat_candidates(
            payload_texts + dom_texts,
            prompt=prompt,
            baseline=baseline,
        )
        terminal_error = self._find_terminal_error(payloads)
        return {
            "conversation_id": conversation_id,
            "text": candidates[-1] if candidates else "",
            "candidates": candidates[-8:],
            "payloads": payloads[-10:],
            "terminal_error": terminal_error,
        }

    async def _collect_result_snapshot(self, kind: str) -> dict[str, Any]:
        page = await self.require_page()
        conversation_id = self._conversation_id_from_url(page.url)
        payloads = list(self._last_responses[-30:])
        if conversation_id:
            try:
                detail = await self.browser_json("GET", f"/api/v1/session-detail?conversationId={conversation_id}")
                payloads.append({"url": "session-detail", "body": detail})
            except Exception as exc:
                payloads.append({"url": "session-detail", "error": str(exc)})
        dom_urls = await page.evaluate(
            """() => {
              const urls = [];
              for (const el of [...document.querySelectorAll('img,video,source,a')]) {
                const url = el.currentSrc || el.src || el.href;
                if (url && /^https?:/.test(url)) urls.push(url);
              }
              return [...new Set(urls)];
            }"""
        )
        urls = classify_media_urls({"payloads": payloads, "dom_urls": dom_urls}, kind)
        urls = [url for url in urls if not self._is_static_asset(url)]
        terminal_error = self._find_terminal_error(payloads)
        return {
            "conversation_id": conversation_id,
            "urls": urls,
            "payloads": payloads[-10:],
            "terminal_error": terminal_error,
        }

    async def _dom_text_candidates(self) -> list[str]:
        page = await self.require_page()
        return await page.evaluate(
            """() => {
              const selectors = [
                '[class*="message"]',
                '[class*="chat"]',
                '[class*="markdown"]',
                '[class*="answer"]',
                '[class*="content"]',
                'main',
                'article'
              ];
              const nodes = new Set();
              for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) nodes.add(el);
              }
              const texts = [];
              for (const el of nodes) {
                const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                if (text && text.length <= 4000) texts.push(text);
              }
              return [...new Set(texts)];
            }"""
        )

    async def _record_response(self, response: Any) -> None:
        url = response.url
        if "/api/v1/" not in url:
            return
        interesting = any(key in url for key in ("task-check", "session-detail", "chat-completion", "configList"))
        if not interesting:
            return
        try:
            text = await response.text()
            try:
                body: Any = json.loads(text)
            except json.JSONDecodeError:
                body = text[:4000]
            self._last_responses.append({"status": response.status, "url": url, "body": body})
            self._last_responses[:] = self._last_responses[-80:]
        except Exception:
            return

    @classmethod
    def _filter_chat_candidates(cls, texts: list[str], *, prompt: str, baseline: set[str]) -> list[str]:
        filtered: list[str] = []
        prompt_norm = cls._normalize_text(prompt)
        blocked_fragments = (
            "longcat",
            "请输入你的问题或需求",
            "开启新对话",
            "新对话",
            "图片生成",
            "视频生成",
            "联网搜索",
            "深度思考",
            "深度研究",
            "下载手机应用",
            "api 开放平台",
            "内容由ai生成",
            "已搜到",
            "页面信息已失效",
            "当前页面停留了太长时间",
        )
        for text in texts:
            normalized = cls._normalize_text(text)
            lowered = normalized.lower()
            if not normalized:
                continue
            if normalized in baseline:
                continue
            if prompt_norm and (normalized == prompt_norm or prompt_norm in normalized):
                continue
            if len(normalized) < 2:
                continue
            if any(fragment in lowered for fragment in blocked_fragments):
                continue
            if normalized not in filtered:
                filtered.append(normalized)
        return filtered

    @classmethod
    def _payload_text_candidates(cls, payloads: Any) -> list[str]:
        candidates: list[str] = []
        text_keys = {"content", "text", "answer", "message", "msg", "reply", "markdown", "delta"}

        def walk(value: Any, parent_key: str = "") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    key_text = str(key)
                    if isinstance(item, str) and key_text.lower() in text_keys:
                        text = cls._normalize_text(item)
                        if text:
                            candidates.append(text)
                    walk(item, key_text)
            elif isinstance(value, list):
                for item in value:
                    walk(item, parent_key)
            elif isinstance(value, str) and parent_key.lower() in text_keys:
                text = cls._normalize_text(value)
                if text:
                    candidates.append(text)

        walk(payloads)
        return candidates

    @staticmethod
    def _normalize_text(text: Any) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    @staticmethod
    def _conversation_id_from_url(url: str) -> str:
        match = re.search(r"/(?:c|ac|v)/([^/?#]+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _is_static_asset(url: str) -> bool:
        lowered = url.lower()
        return any(host in lowered for host in ("s3.meituan.net/static", "serverless.sankuai.com/dx-avatar"))

    @staticmethod
    def _find_terminal_error(payloads: list[dict[str, Any]]) -> str:
        markers = ("失败", "无权限", "额度不足", "次数", "quota", "forbidden", "error", "页面信息已失效")
        text = json.dumps(payloads, ensure_ascii=False).lower()
        if any(marker.lower() in text for marker in markers):
            # Do not mark every transient stream error as terminal. Return only clear provider failures.
            for marker in ("额度不足", "无权限", "次数已用完", "quota exhausted", "quota exceeded", "页面信息已失效"):
                if marker in text:
                    return f"LongCat provider reported terminal error: {marker}"
        return ""

    def _clear_stale_profile_locks(self) -> None:
        profile = Path(self.user_data_dir)
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            path = profile / name
            try:
                if path.exists() or path.is_symlink():
                    path.unlink()
            except Exception:
                pass


def data_root() -> str:
    explicit = os.environ.get("LONGCAT_DATA_DIR")
    if explicit:
        return explicit
    return "/app/data" if os.path.isdir("/app") else os.path.join(os.getcwd(), "data")
