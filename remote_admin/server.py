"""Small owner-only cover CMS. Reverse proxy the admin listener over HTTPS only."""
import argparse
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading
import time
from urllib.parse import urlsplit

try:
    from catalog import read_catalog, validate_choice
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'manage'))
    from catalog import read_catalog, validate_choice

COOKIE = '__Host-forest_admin'
SETUP_COOKIE = 'forest_setup'
SESSION_SECONDS = 8 * 3600
ASSETS = Path(__file__).resolve().parent
HASH_SLOTS = threading.BoundedSemaphore(2)


class PasswordError(ValueError):
    pass


class RateLimited(ValueError):
    pass


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def csrf(token):
    return hmac.new(token.encode(), b'forest-csrf-v1', hashlib.sha256).hexdigest()


def password_hash(password, salt):
    if not HASH_SLOTS.acquire(blocking=False):
        raise RateLimited('请求过多，请稍后重试。')
    try:
        return hashlib.scrypt(password.encode(), salt=salt, n=2**17, r=8, p=1, dklen=64, maxmem=256 * 1024 * 1024)
    finally:
        HASH_SLOTS.release()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.login_lock = threading.Lock()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, salt BLOB NOT NULL, hash BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (hash TEXT PRIMARY KEY, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, ip TEXT NOT NULL, time REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS covers (album TEXT PRIMARY KEY, file TEXT NOT NULL);
            ''')
        if os.name == 'posix':
            os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def has_admin(self):
        with self.db() as db:
            return db.execute('SELECT 1 FROM admin').fetchone() is not None

    def setup(self, username, password):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', username):
            raise PasswordError('账号需为 3–40 位字母、数字、点、下划线或短横线。')
        if not isinstance(password, str) or not 14 <= len(password) <= 128 or len(set(password)) < 6:
            raise PasswordError('密码需为 14–128 位，至少包含 6 种不同字符。建议使用随机密码或长口令。')
        if self.has_admin():
            raise PasswordError('管理员已设置。')
        salt = secrets.token_bytes(32)
        hashed = password_hash(password, salt)
        try:
            with self.db() as db:
                db.execute('INSERT INTO admin VALUES (1, ?, ?, ?)', (username, salt, hashed))
        except sqlite3.IntegrityError:
            raise PasswordError('管理员已设置。') from None

    def login(self, username, password, ip):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 128 or len(password) > 128:
            raise PasswordError('账号或密码不正确。')
        # Reserve attempts before expensive hashing; both per-IP and global bounds persist across restarts.
        with self.login_lock, self.db() as db:
            now = time.time()
            db.execute('DELETE FROM attempts WHERE time < ?', (now - 900,))
            count = db.execute('SELECT COUNT(*) FROM attempts WHERE ip=?', (ip,)).fetchone()[0]
            total = db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
            if count >= 5 or total >= 30:
                raise RateLimited('登录尝试过多，请 15 分钟后重试。')
            attempt = db.execute('INSERT INTO attempts(ip,time) VALUES (?,?)', (ip, now)).lastrowid
            admin = db.execute('SELECT username,salt,hash FROM admin').fetchone()
        # Unknown usernames follow the same hash path. No public endpoint creates an account.
        hashed = password_hash(password, admin[1] if admin else b'forest-unconfigured-placeholder')
        if not admin or not hmac.compare_digest(digest(username), digest(admin[0])) or not hmac.compare_digest(hashed, admin[2]):
            raise PasswordError('账号或密码不正确。')
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM attempts WHERE id=?', (attempt,))
            db.execute('DELETE FROM sessions WHERE expires <= ?', (time.time(),))
            # Bound live sessions; oldest session expires when a ninth device logs in.
            db.execute('DELETE FROM sessions WHERE hash IN (SELECT hash FROM sessions ORDER BY expires DESC LIMIT -1 OFFSET 7)')
            db.execute('INSERT INTO sessions VALUES (?,?)', (digest(token), time.time() + SESSION_SECONDS))
        return token

    def session_valid(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return False
        with self.db() as db:
            return db.execute('SELECT 1 FROM sessions WHERE hash=? AND expires>?', (digest(token), time.time())).fetchone() is not None

    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (digest(token),))

    def covers(self):
        with self.db() as db:
            return dict(db.execute('SELECT album,file FROM covers'))

    def set_cover(self, album, file):
        with self.db() as db:
            db.execute('INSERT INTO covers VALUES (?,?) ON CONFLICT(album) DO UPDATE SET file=excluded.file', (album, file))


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, handler):
        if address[0] != '127.0.0.1':
            raise ValueError('Only loopback listeners are permitted.')
        self.slots = threading.BoundedSemaphore(24)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Never dump a request, credential or session into the journal.
        print('Admin request failed.', file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    server_version = 'Forest'
    sys_version = ''

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def reply(self, status, payload, mime='application/json; charset=utf-8', extra=None):
        raw = json.dumps(payload, ensure_ascii=False).encode() if mime.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://denss.asia; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def fail(self, status, message):
        self.reply(status, {'error': message})

    def cookie(self, name):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            return cookies[name].value if name in cookies else ''
        except Exception:
            return ''

    def body(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json' or self.headers.get('Transfer-Encoding'):
            raise ValueError('请求格式无效。')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 4096:
            raise ValueError('请求大小无效。')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('请求格式无效。')
        return data

    def do_GET(self):
        try:
            self.get()
        except (OSError, ValueError, sqlite3.Error):
            self.fail(503, '服务暂时不可用，请稍后重试。')

    def do_POST(self):
        try:
            self.post()
        except RateLimited as error:
            self.reply(429, {'error': str(error)}, extra={'Retry-After': '900'})
        except PasswordError as error:
            self.fail(401, str(error))
        except (ValueError, UnicodeError):
            self.fail(422, '请求无效，请检查输入。')
        except (OSError, sqlite3.Error):
            self.fail(503, '保存失败，请稍后重试。')


class AdminServer(Server):
    def __init__(self, address, store, root, origin):
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Canonical origin must use HTTPS.')
        self.store, self.root, self.origin, self.host = store, Path(root), origin, parsed.netloc
        super().__init__(address, AdminHandler)

    def catalog(self):
        albums, photos = read_catalog(self.root)
        overrides = self.store.covers()
        for album in albums:
            choice = overrides.get(album['id'])
            if choice:
                try:
                    validate_choice(self.root, album['id'], choice)
                    album['cover'] = choice
                except ValueError:
                    pass  # Removed photographs fall back to the versioned default.
        return albums, photos


class AdminHandler(Handler):
    def host_ok(self):
        if self.headers.get('Host') != self.server.host:
            self.fail(403, '请通过管理域名访问。')
            return False
        return True

    def auth(self, mutate=False):
        token = self.cookie(COOKIE)
        if not self.server.store.session_valid(token):
            self.fail(401, '请先登录。')
            return None
        if mutate and (self.headers.get('Origin') != self.server.origin or not hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode(), csrf(token).encode())):
            self.fail(403, '请求校验失败，请刷新后重试。')
            return None
        return token

    def get(self):
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        if path == '/api/covers':
            albums, _ = self.server.catalog()
            headers = {'Vary': 'Origin'}
            if self.headers.get('Origin') == 'https://chenforest-love.github.io':
                headers['Access-Control-Allow-Origin'] = 'https://chenforest-love.github.io'
            return self.reply(200, {'covers': {a['id']: a['cover'] for a in albums}}, extra=headers)
        if path == '/api/admin/state':
            token = self.auth()
            if token:
                albums, photos = self.server.catalog()
                return self.reply(200, {'csrf': csrf(token), 'albums': albums, 'photos': photos})
            return
        files = {'/admin/': ('admin.html', 'text/html; charset=utf-8'), '/api/admin/assets/admin.css': ('admin.css', 'text/css; charset=utf-8'), '/api/admin/assets/admin.js': ('admin.js', 'text/javascript; charset=utf-8')}
        if path in files:
            file, mime = files[path]
            return self.reply(200, (ASSETS / file).read_bytes(), mime)
        self.fail(404, '页面不存在。')

    def post(self):
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        if path not in ['/api/admin/login', '/api/admin/logout', '/api/admin/cover']:
            return self.fail(404, '页面不存在。')
        if self.headers.get('Origin') != self.server.origin:
            return self.fail(403, '请求来源无效。')
        if path == '/api/admin/login':
            data = self.body()
            ip = self.headers.get('X-Real-IP', self.client_address[0])
            try:
                ip = str(ipaddress.ip_address(ip))
            except ValueError:
                ip = self.client_address[0]
            token = self.server.store.login(data.get('username'), data.get('password'), ip)
            return self.reply(200, {'csrf': csrf(token)}, extra={'Set-Cookie': f'{COOKIE}={token}; Path=/; Max-Age={SESSION_SECONDS}; Secure; HttpOnly; SameSite=Strict'})
        token = self.auth(mutate=True)
        if not token:
            return
        data = self.body()
        if path.endswith('/logout'):
            self.server.store.logout(token)
            return self.reply(200, {'ok': True}, extra={'Set-Cookie': f'{COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict'})
        album, file = data.get('album'), data.get('file')
        validate_choice(self.server.root, album, file)
        self.server.store.set_cover(album, file)
        self.reply(200, {'ok': True})


class SetupServer(Server):
    def __init__(self, address, store, tunnel_port=None):
        self.store, self.tokens, self.lock = store, {}, threading.Lock()
        self.tunnel_port = tunnel_port
        super().__init__(address, SetupHandler)


class SetupHandler(Handler):
    def ready(self):
        if self.server.store.has_admin():
            self.fail(410, '管理员已设置，此入口已关闭。请使用网站管理页登录。')
            return False
        ports = {self.server.server_port, self.server.tunnel_port}
        allowed = {f'127.0.0.1:{p}' for p in ports if p}
        if self.headers.get('Host') not in allowed:
            self.fail(403, '仅允许 SSH 转发的本机设置入口。')
            return False
        return True

    def valid_token(self):
        token = self.cookie(SETUP_COOKIE)
        with self.server.lock:
            expiry = self.server.tokens.get(digest(token), 0)
        return token if expiry > time.time() else None

    def get(self):
        if not self.ready():
            return
        path = urlsplit(self.path).path
        if path == '/':
            token = secrets.token_urlsafe(32)
            with self.server.lock:
                self.server.tokens = {k: v for k, v in self.server.tokens.items() if v > time.time()}
                if len(self.server.tokens) >= 32:
                    return self.fail(429, '请稍后重试。')
                self.server.tokens[digest(token)] = time.time() + 900
            return self.reply(200, (ASSETS / 'setup.html').read_bytes(), 'text/html; charset=utf-8', {'Set-Cookie': f'{SETUP_COOKIE}={token}; Path=/; Max-Age=900; HttpOnly; SameSite=Strict'})
        if path == '/state':
            token = self.valid_token()
            if not token:
                return self.fail(403, '请刷新设置页。')
            return self.reply(200, {'csrf': csrf(token)})
        files = {'/setup.js': ('setup.js', 'text/javascript; charset=utf-8'), '/admin.css': ('admin.css', 'text/css; charset=utf-8')}
        if path in files:
            file, mime = files[path]
            return self.reply(200, (ASSETS / file).read_bytes(), mime)
        self.fail(404, '页面不存在。')

    def post(self):
        if not self.ready():
            return
        if self.path != '/setup':
            return self.fail(404, '页面不存在。')
        token = self.valid_token()
        if not token or self.headers.get('Origin') != 'http://' + self.headers['Host'] or not hmac.compare_digest(self.headers.get('X-CSRF-Token', '').encode(), csrf(token).encode()):
            return self.fail(403, '请求校验失败，请刷新设置页。')
        data = self.body()
        if data.get('password') != data.get('confirm'):
            return self.fail(422, '两次输入的密码不一致。')
        self.server.store.setup(data.get('username'), data.get('password'))
        with self.server.lock:
            self.server.tokens.clear()
        self.reply(200, {'ok': True}, extra={'Set-Cookie': f'{SETUP_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--origin', default='https://denss.asia')
    parser.add_argument('--port', type=int, default=6190)
    parser.add_argument('--setup-port', type=int, default=6191)
    parser.add_argument('--tunnel-port', type=int, default=4190)
    args = parser.parse_args()
    os.umask(0o077)
    store = Store(args.database)
    server = AdminServer(('127.0.0.1', args.port), store, args.root, args.origin)
    if not store.has_admin():
        setup = SetupServer(('127.0.0.1', args.setup_port), store, args.tunnel_port)
        threading.Thread(target=setup.serve_forever, daemon=True).start()
    server.serve_forever()


if __name__ == '__main__':
    main()
