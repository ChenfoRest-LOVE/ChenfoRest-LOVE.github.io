"""Same-origin reader API; HTTP development is restricted to loopback."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import threading
from urllib.parse import parse_qs, unquote, urlsplit

from store import Problem, Store, SESSION_SECONDS, csrf

ROOT = Path(__file__).resolve().parents[1]
PREFIX = '/api/community/'


class CommunityServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, store, root, origin=None, trust_proxy=False):
        if address[0] != '127.0.0.1':
            raise ValueError('Only loopback listeners are permitted.')
        if origin:
            parsed = urlsplit(origin)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment or parsed.netloc != parsed.netloc.lower()):
                raise ValueError('Production origin must be a canonical HTTPS origin without a path.')
        if trust_proxy and not origin:
            raise ValueError('Proxy headers are only supported behind production HTTPS.')
        self.root, self.store = Path(root).resolve(), store
        if store.path.resolve().is_relative_to(self.root):
            raise ValueError('Account database must be outside the public repository.')
        self.trust_proxy, self.secure = trust_proxy, bool(origin)
        self.cookie_name = '__Host-forest_reader' if self.secure else 'forest_reader_dev'
        self.slots = threading.BoundedSemaphore(24)
        super().__init__(address, Handler)
        self.origin = origin or f'http://127.0.0.1:{self.server_port}'
        self.host = urlsplit(self.origin).netloc

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        print('Reader request failed.', file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    server_version = 'Forest'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(10)
        self.body_read = False

    def log_message(self, *args):
        pass  # Do not log URLs, headers, credentials or comment bodies.

    def reply(self, status, payload, mime='application/json; charset=utf-8', cookie=None):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        if mime.startswith('application/json'):
            self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
        if cookie:
            secure = '; Secure' if self.server.secure else ''
            value, lifetime = cookie
            self.send_header('Set-Cookie', f'{self.server.cookie_name}={value}; Path=/; Max-Age={lifetime}; HttpOnly; SameSite=Strict{secure}')
        if status == 429:
            self.send_header('Retry-After', '60')
        self.end_headers()
        self.wfile.write(raw)

    def token(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            return cookies[self.server.cookie_name].value if self.server.cookie_name in cookies else ''
        except Exception:
            return ''

    def validate_host(self):
        if self.headers.get_all('Host') != [self.server.host]:
            raise Problem(403, '请求地址无效。')

    def user(self, mutate=False):
        token = self.token()
        user = self.server.store.session(token)
        if mutate:
            if not user:
                raise Problem(401, '请先登录。')
            supplied = self.headers.get('X-CSRF-Token', '')
            if not hmac.compare_digest(supplied.encode(), csrf(token).encode()):
                raise Problem(403, '登录状态校验失败，请刷新后重试。')
        return user

    def ip(self):
        if self.server.trust_proxy:
            try:
                return str(ipaddress.ip_address(self.headers.get('X-Real-IP', '')))
            except ValueError:
                raise Problem(403, '反向代理配置无效。') from None
        return self.client_address[0]

    def body(self):
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise Problem(422, '请求格式无效。')
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise Problem(415, '请求需使用 JSON。')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 4096:
            raise Problem(413, '请求过大或为空。')
        self.body_read = True
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise Problem(422, '请求不完整。')
        data = json.loads(raw.decode('utf-8'))
        if not isinstance(data, dict):
            raise Problem(422, '请求格式无效。')
        return data

    def discard_rejected_body(self):
        # Closing a socket with an unread later body packet can turn an HTTP
        # 4xx into a TCP reset on Windows. Drain only bounded, framed bodies;
        # never decode or process them, and never wait indefinitely for them.
        if self.command != 'POST' or self.body_read or self.headers.get('Transfer-Encoding'):
            return
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1:
            return
        try:
            length = int(lengths[0])
            if 0 < length <= 65536:
                self.connection.settimeout(1)
                self.body_read = True
                self.rfile.read(length)
        except (ValueError, OSError):
            pass

    def dispatch(self, method):
        try:
            self.validate_host()
            if method == 'GET':
                self.get()
            else:
                if (self.headers.get_all('Origin') != [self.server.origin]
                        or self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin', 'none')):
                    raise Problem(403, '请求来源无效。')
                self.post()
        except Problem as error:
            self.discard_rejected_body()
            self.reply(error.status, {'error': str(error)})
        except (ValueError, UnicodeError, OverflowError):
            self.discard_rejected_body()
            self.reply(422, {'error': '请求无效，请检查输入。'})
        except (OSError, sqlite3.Error):
            self.reply(503, {'error': '服务暂时不可用，请稍后重试。'})

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def get(self):
        parsed = urlsplit(self.path)
        if parsed.path == PREFIX + 'health':
            return self.reply(200, {'app': 'forest-comments', 'version': 1})
        if parsed.path == PREFIX + 'session':
            user = self.user()
            return self.reply(200, {'user': user, 'csrf': csrf(self.token()) if user else None})
        if parsed.path == PREFIX + 'comments':
            query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=4)
            if any(len(values) != 1 for values in query.values()):
                raise Problem(422, '查询参数无效。')
            before = int(query['before'][0]) if 'before' in query else None
            return self.reply(200, self.server.store.list(query.get('article', [''])[0], self.user(), before))
        if parsed.path.startswith(PREFIX):
            raise Problem(404, '接口不存在。')
        self.static(parsed.path)

    def post(self):
        path = urlsplit(self.path).path
        data = self.body()
        if path in (PREFIX + 'register', PREFIX + 'login'):
            operation = self.server.store.register if path.endswith('register') else self.server.store.login
            token = operation(data.get('username'), data.get('password'), self.ip())
            return self.reply(201 if path.endswith('register') else 200,
                              {'user': self.server.store.session(token), 'csrf': csrf(token)},
                              cookie=(token, SESSION_SECONDS))
        if path == PREFIX + 'logout':
            self.user(mutate=True)
            self.server.store.logout(self.token())
            return self.reply(200, {'ok': True}, cookie=('', 0))
        if path == PREFIX + 'comments':
            item = self.server.store.post(data.get('article'), data.get('text'), self.user(mutate=True), self.ip())
            return self.reply(201, item)
        match = re.fullmatch(r'/api/community/comments/([1-9][0-9]{0,17})/delete', path)
        if match:
            self.server.store.delete(int(match[1]), self.user(mutate=True))
            return self.reply(200, {'ok': True})
        raise Problem(404, '接口不存在。')

    def static(self, url_path):
        path = unquote(url_path)
        if path == '/assets/comments-config.js':
            return self.reply(200, b'window.FOREST_COMMENTS = Object.freeze({enabled: true});\n', 'text/javascript; charset=utf-8')
        if path == '/':
            path = '/index.html'
        parts = PurePosixPath(path).parts[1:]
        if not parts or '\\' in path or any(part.startswith('.') for part in parts):
            raise Problem(404, '文件不存在。')
        if len(parts) == 1:
            allowed = parts[0] in {'index.html', 'photos.html', 'writing.html', 'reading.html', 'projects.html'}
        else:
            allowed = parts[0] in {'assets', 'content'}
        target = (self.server.root / Path(*parts)).resolve()
        suffixes = {'.html', '.css', '.js', '.webp', '.jpg', '.jpeg', '.png', '.svg', '.json', '.woff2', '.ico'}
        if not allowed or not target.is_relative_to(self.server.root) or target.suffix not in suffixes or not target.is_file():
            raise Problem(404, '文件不存在。')
        if target.stat().st_size > 40 * 1024 * 1024:
            raise Problem(413, '文件过大。')
        mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        if target.suffix in {'.html', '.css', '.js', '.json'}:
            mime += '; charset=utf-8'
        self.reply(200, target.read_bytes(), mime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4192)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--origin', help='Future production HTTPS origin; omit for loopback development')
    parser.add_argument('--trust-proxy', action='store_true')
    args = parser.parse_args()
    base = Path(os.environ['LOCALAPPDATA']) / 'ForestComments' if os.name == 'nt' else Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'forest-comments'
    articles = json.loads(Path(__file__).with_name('articles.json').read_text('utf-8'))
    store = Store(args.data or base / 'community.sqlite', articles)
    server = CommunityServer(('127.0.0.1', args.port), store, args.root, args.origin, args.trust_proxy)
    print(f'Forest comments preview: {server.origin}/writing.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
