"""Caption web server - HTTP + WebSocket delivery."""

import asyncio
import io
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import qrcode
from aiohttp import web

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class CaptionMessage:
    text: str
    language: str
    timestamp: float
    sequence_number: int


class CaptionServer:
    def __init__(self, port: int, max_history: int, max_clients: int, admin_pin: str, reconnect_timeout: int = 600, site_title: str = "Live Captions", secondary_title: str = "Live Captions"):
        self._port = port
        self._max_history = max_history
        self._max_clients = max_clients
        self._admin_pin = admin_pin
        self._reconnect_timeout = reconnect_timeout
        self._site_title = site_title
        self._secondary_title = secondary_title
        self._clients: set[web.WebSocketResponse] = set()
        self._history: list[CaptionMessage] = []
        self._sequence = 0
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._start_time = time.time()
        # Shared state for status page
        self._current_language = "en"
        self._model_name = ""
        self._audio_level = -100.0
        self._max_audio_level = -100.0
        # Audio broadcaster (set externally if enabled)
        self._audio_broadcaster = None

    def set_status(self, language: str, model_name: str, audio_level: float):
        self._current_language = language
        self._model_name = model_name
        self._audio_level = audio_level
        if audio_level > self._max_audio_level:
            self._max_audio_level = audio_level

    def set_audio_broadcaster(self, broadcaster) -> None:
        """Attach the audio broadcaster for /ws/audio and /listen routes."""
        self._audio_broadcaster = broadcaster

    async def start(self) -> None:
        self._app = web.Application()
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/ws", self._handle_websocket)
        self._app.router.add_get("/display", self._handle_display)
        self._app.router.add_get("/status", self._handle_status)
        self._app.router.add_get("/qr", self._handle_qr_page)
        self._app.router.add_get("/qr-ip", self._handle_qr_ip_page)
        self._app.router.add_get("/qr.png", self._handle_qr)
        self._app.router.add_get("/qr-ip.png", self._handle_qr_ip)
        self._app.router.add_post("/admin/language", self._handle_set_language)
        if self._audio_broadcaster:
            self._app.router.add_get("/ws/audio", self._audio_broadcaster.handle_websocket)
            self._app.router.add_get("/listen", self._handle_listen)
        self._app.router.add_static("/static", STATIC_DIR)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info(f"Caption server listening on port {self._port}")

    async def stop(self) -> None:
        for ws in list(self._clients):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()

    async def broadcast(self, text: str, language: str) -> None:
        self._sequence += 1
        msg = CaptionMessage(
            text=text,
            language=language,
            timestamp=time.time(),
            sequence_number=self._sequence,
        )
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        payload = json.dumps(asdict(msg))
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # --- Language change callback (set by main loop) ---
    _on_language_change = None

    def set_language_callback(self, cb):
        self._on_language_change = cb

    # --- HTTP Handlers ---

    async def _handle_index(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "index.html").read_text()
        html = html.replace("{{SITE_TITLE}}", self._site_title)
        return web.Response(text=html, content_type="text/html")

    async def _handle_display(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "display.html").read_text()
        html = html.replace("{{SITE_TITLE}}", self._site_title)
        html = html.replace("{{SECONDARY_TITLE}}", self._secondary_title)
        html = html.replace(
            "/*CONFIG*/",
            f"const RECONNECT_TIMEOUT = {self._reconnect_timeout};"
        )
        return web.Response(text=html, content_type="text/html")

    async def _handle_listen(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "listen.html").read_text()
        html = html.replace("{{SITE_TITLE}}", self._site_title)
        return web.Response(text=html, content_type="text/html")

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        if len(self._clients) >= self._max_clients:
            return web.Response(status=503, text="Too many clients")

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._clients.add(ws)

        # Send history
        for msg in self._history[-10:]:
            await ws.send_str(json.dumps(asdict(msg)))

        try:
            async for _ in ws:
                pass  # We don't expect client messages
        finally:
            self._clients.discard(ws)

        return ws

    async def _handle_status(self, request: web.Request) -> web.Response:
        pin = request.query.get("pin", "")
        if pin != self._admin_pin:
            return web.json_response({"error": "Invalid PIN"}, status=403)

        uptime = int(time.time() - self._start_time)
        level = float(self._audio_level)
        if not math.isfinite(level):
            level = -100.0
        data = {
            "connected_clients": len(self._clients),
            "language": self._current_language,
            "model": self._model_name,
            "current_audio_level_db": round(level, 1),
            "max_audio_level_db": round(float(self._max_audio_level), 1),
            "uptime_seconds": uptime,
        }
        return web.json_response(data)

    async def _handle_qr_page(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "qr.html").read_text()
        html = html.replace("{{SITE_TITLE}}", self._site_title)
        return web.Response(text=html, content_type="text/html")

    async def _handle_qr_ip_page(self, request: web.Request) -> web.Response:
        html = (STATIC_DIR / "qr-ip.html").read_text()
        html = html.replace("{{SITE_TITLE}}", self._site_title)
        return web.Response(text=html, content_type="text/html")

    async def _handle_qr(self, request: web.Request) -> web.Response:
        import socket
        hostname = socket.gethostname()
        url = f"http://{hostname}.local:{self._port}/"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return web.Response(body=buf.getvalue(), content_type="image/png")

    async def _handle_qr_ip(self, request: web.Request) -> web.Response:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        url = f"http://{ip}:{self._port}/"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return web.Response(body=buf.getvalue(), content_type="image/png")

    async def _handle_set_language(self, request: web.Request) -> web.Response:
        pin = request.headers.get("X-Admin-Pin", "")
        if pin != self._admin_pin:
            return web.json_response({"error": "Invalid PIN"}, status=403)
        body = await request.json()
        lang = body.get("language")
        if lang not in ("en", "es", "auto"):
            return web.json_response({"error": "Invalid language"}, status=400)
        self._current_language = lang
        if self._on_language_change:
            self._on_language_change(lang)
        return web.json_response({"language": lang})
