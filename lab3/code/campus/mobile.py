"""Start the loopback-only backend for the Android WebView client."""

import argparse
import http.cookies
import http.server
import json
import logging
import mimetypes
import pathlib
import re
import sqlite3
import urllib.parse
import webbrowser

from campus import domain
from campus import mobile_api
from campus import storage

_STATIC = pathlib.Path(__file__).with_name("mobile_ui")
_COOKIE = "campus_session"


class LocalServer(http.server.ThreadingHTTPServer):
    """Serve the marketplace on this machine or through adb reverse."""

    daemon_threads = True

    def __init__(self, address, api):
        super().__init__(address, Handler)
        self.api = api


class Handler(http.server.BaseHTTPRequestHandler):
    """Serve UTF-8 JSON, the UI, and authorized product images."""

    # Handler names are dispatched by BaseHTTPRequestHandler.
    # pylint: disable=invalid-name
    def do_GET(self):
        """Route safe read requests."""
        if not self._valid_host():
            self._json(403, {"error": "仅允许访问本机地址"})
            return
        path = urllib.parse.urlsplit(self.path).path
        try:
            self._read(path)
        except domain.RuleError as error:
            self._json(404, {"error": str(error)})
        except sqlite3.Error:
            self._server_error()

    def do_POST(self):
        """Reject cross-origin and oversized requests before dispatch."""
        if not self._valid_host() or not self._valid_origin():
            self._json(403, {"error": "请求来源不受信任"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"error": "请求须使用 JSON"})
            return
        path = urllib.parse.urlsplit(self.path).path
        action = re.fullmatch(r"/api/([a-z]+)", path)
        if action is None:
            self._json(404, {"error": "接口不存在"})
            return
        try:
            data = self._body()
            result = self.server.api.call(self._token(), action[1], data)
            self._respond(result)
        except (ValueError, UnicodeError):
            self._json(400, {"error": "请求数据无效或过大"})
        except domain.RuleError as error:
            self._json(409, {"error": str(error)})
        except (OSError, sqlite3.Error):
            self._server_error()

    def _read(self, path):
        if path == "/api/session":
            self._json(200, self.server.api.session(self._token()))
            return
        match = re.fullmatch(r"/media/(\d{1,15})/(\d{1,2})", path)
        if match:
            data = self.server.api.image(
                self._token(), int(match[1]), int(match[2]),
            )
            content_type = (
                "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
            )
            self._send(200, data, content_type)
            return
        name = "index.html" if path == "/" else path.lstrip("/")
        if not re.fullmatch(r"(?:assets/)?[a-zA-Z0-9_.-]+", name):
            self.send_error(404)
            return
        asset = _STATIC / name
        if not asset.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(asset.name)[0]
        if asset.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        content_type = content_type or "application/octet-stream"
        self._send(200, asset.read_bytes(), content_type)

    def _valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {
            f"127.0.0.1:{port}", f"localhost:{port}",
        }

    def _valid_origin(self):
        return self.headers.get("Origin") == (
            "http://" + self.headers.get("Host", "")
        )

    def _token(self):
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except http.cookies.CookieError:
            return None
        item = cookie.get(_COOKIE)
        return item.value if item else None

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 36_000_000:
            raise ValueError("invalid body size")
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError("expected object")
        return data

    def _respond(self, result):
        if isinstance(result, dict) and "session_token" in result:
            token = result["session_token"]
            age = 28800 if token else 0
            cookie = f"{_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict"
            headers = {"Set-Cookie": f"{cookie}; Max-Age={age}"}
            self._json(200, {"ok": True}, headers)
        else:
            self._json(200, result)

    def _server_error(self):
        logging.exception("本地后端操作失败")
        self._json(500, {"error": "本地服务暂时无法处理，请重试"})

    def _json(self, status, data, headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8", headers)

    def _send(self, status, data, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)


def main():
    """Run the desktop backend and its reservation expiry worker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8871)
    parser.add_argument("--db", default="data/mobile.sqlite3")
    parser.add_argument("--deadline", type=int, default=86400)
    parser.add_argument("--open", action="store_true",
                        help="同时打开电脑版浏览器")
    args = parser.parse_args()
    if args.deadline <= 0 or not 0 <= args.port <= 65535:
        parser.error("预约时限须为正数，端口须在 0 至 65535 之间")
    database = storage.Database(args.db)
    database.initialize()
    api = mobile_api.Api(database, args.deadline)
    try:
        server = LocalServer(("127.0.0.1", args.port), api)
    except OSError as error:
        parser.exit(1, f"后端无法使用端口 {args.port}：{error}\n")
    with server:
        print(f"校园拾光：http://127.0.0.1:{server.server_port}", flush=True)
        print(f"安卓 USB 联调：adb reverse tcp:8871 tcp:{server.server_port}",
              flush=True)
        if args.open:
            webbrowser.open(f"http://127.0.0.1:{server.server_port}/")
        with api.services.trades.expiry_worker():
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
