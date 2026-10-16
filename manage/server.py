"""Owner-only loopback manager; credentials stay in the existing local tools."""
import argparse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import threading
from urllib.parse import unquote, urlsplit

from catalog import ALBUMS, atomic_write, read_catalog, set_cover, validate_choice

COVER_FILES = {ALBUMS, 'photos.html'}
ORIGINS = {'https://github.com/ChenfoRest-LOVE/ChenfoRest-LOVE.github.io.git', 'git@github.com:ChenfoRest-LOVE/ChenfoRest-LOVE.github.io.git'}


class PublishError(Exception):
    def __init__(self, step, message):
        super().__init__(message)
        self.step = step


def run_command(args, timeout=90):
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'}
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, timeout=timeout, env=env).stdout.strip()


class Publisher:
    def __init__(self, root, runner=run_command):
        self.root = root
        self.run = runner

    def git(self, *args):
        return self.run(['git', '-C', str(self.root), *args])

    def publish(self, album, file):
        validate_choice(self.root, album, file)
        step = 'check'
        before = written = None
        before_head = None
        try:
            if self.git('branch', '--show-current') != 'main':
                raise PublishError(step, '请先完成当前开发并切回 main 分支，再发布封面。')
            if self.git('status', '--porcelain', '--untracked-files=normal'):
                raise PublishError(step, '工作区有未提交修改，请先处理后再发布封面。')
            if self.git('remote', 'get-url', 'origin') not in ORIGINS:
                raise PublishError(step, '当前仓库不是已配置的个人网站，已停止发布。')
            step = 'fetch'
            self.git('fetch', 'origin', 'main')
            self.git('merge', '--ff-only', 'origin/main')
            # Retry our own pending cover commits, but never publish unrelated work.
            for commit in self.git('rev-list', 'origin/main..HEAD').splitlines():
                paths = set(self.git('diff-tree', '--no-commit-id', '--name-only', '-r', commit).splitlines())
                subject = self.git('show', '-s', '--format=%s', commit)
                if not paths or not paths <= COVER_FILES or not subject.startswith('Set album cover: '):
                    raise PublishError('check', '本机有尚未发布的其他提交，请先完成当前开发。')
            step = 'save'
            before_head = self.git('rev-parse', 'HEAD')
            before = {name:(self.root/name).read_text(encoding='utf-8') for name in COVER_FILES}
            changed = set_cover(self.root, album, file)
            if changed:
                written = {name:(self.root/name).read_text(encoding='utf-8') for name in COVER_FILES}
                self.git('add', '--', ALBUMS, 'photos.html')
                name = self.git('log', '-1', '--format=%an')
                email = self.git('log', '-1', '--format=%ae')
                self.git('-c', f'user.name={name}', '-c', f'user.email={email}', 'commit', '--only', '-m', 'Set album cover: ' + album, '--', ALBUMS, 'photos.html')
            step = 'push'
            self.git('push', 'origin', 'main')
            revision = self.git('rev-parse', 'HEAD')
            return {'revision': revision, 'message': '封面已提交 GitHub，腾讯云暂不同步；GitHub Pages 通常需要稍等片刻更新。'}
        except PublishError:
            raise
        except (subprocess.SubprocessError, OSError, RuntimeError) as error:
            if step == 'save' and written is not None:
                try:
                    # Roll back only our own uncommitted writes. A commit that
                    # completed before a timeout is retained for the next retry.
                    if self.git('rev-parse', 'HEAD') == before_head:
                        if any((self.root/name).read_text(encoding='utf-8') != text for name,text in written.items()):
                            raise PublishError('save', '保存期间文件被其他程序修改，已保留现场，请先检查工作区。')
                        self.git('restore', '--staged', '--', ALBUMS, 'photos.html')
                        for name, text in before.items():
                            atomic_write(self.root/name, text)
                except PublishError:
                    raise
                except (subprocess.SubprocessError, OSError, RuntimeError):
                    raise PublishError('save', '本地保存失败且无法自动恢复，请检查工作区后重试。') from error
            messages = {'check':'无法检查本机仓库，请确认 Git 可用。',
                        'fetch':'无法同步 GitHub，请检查网络与本机登录状态。',
                        'save':'无法完成本机封面提交；已保留完成的提交或恢复未提交更改，可重试。',
                        'push':'封面已保存到本机，GitHub 推送失败；检查网络或登录后可重试。'}
            raise PublishError(step, messages[step]) from error


class ManagerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, publisher=None):
        if address[0] != '127.0.0.1':
            raise ValueError('The manager must bind only to 127.0.0.1')
        self.root = Path(root).resolve()
        self.publisher = publisher or Publisher(self.root)
        self.session = secrets.token_urlsafe(32)
        self.csrf = secrets.token_urlsafe(32)
        self.publish_lock = threading.Lock()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Never log cookies, CSRF values, or request bodies.

    def host_ok(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def authenticated(self, write=False):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if not self.host_ok() or self.headers.get('Origin', origin) != origin:
            return False
        if self.headers.get('Sec-Fetch-Site', 'same-origin') not in ['same-origin', 'none']:
            return False
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            value = cookies['forest_manager'].value
        except (KeyError, ValueError):
            return False
        if not hmac.compare_digest(value, self.server.session):
            return False
        return not write or (self.headers.get('Origin') == origin and hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.csrf))

    def send(self, status, body, content_type='application/json; charset=utf-8', session=False):
        if isinstance(body, dict):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        if session:
            self.send_header('Set-Cookie', f'forest_manager={self.server.session}; HttpOnly; SameSite=Strict; Path=/')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {'error':'仅允许本机管理地址。'})
        path = unquote(urlsplit(self.path).path)
        if path == '/_manage/health':
            return self.send(200, {'app':'forest-cover-manager', 'version':2, 'publicationMode':'github-only'})
        if path == '/_manage/state':
            if not self.authenticated():
                return self.send(403, {'error':'请从本机管理入口重新打开。'})
            albums, photos = read_catalog(self.server.root)
            return self.send(200, {'albums':albums, 'photos':photos, 'csrf':self.server.csrf})
        if path == '/_manage/controls.js':
            # Script contains no credentials; state and writes require the local session.
            return self.send(200, (Path(__file__).parent/'controls.js').read_bytes(), 'text/javascript; charset=utf-8')
        parts = PurePosixPath(path).parts
        if any(p.startswith('.') for p in parts) or '\\' in path:
            return self.send(404, {'error':'Not found'})
        relative = path.lstrip('/') or 'photos.html'
        allowed = relative in ['index.html','photos.html','writing.html','reading.html','projects.html'] or relative.startswith(('assets/','content/'))
        target = (self.server.root / relative).resolve()
        if not allowed or not target.is_relative_to(self.server.root) or not target.is_file():
            return self.send(404, {'error':'Not found'})
        body = target.read_bytes()
        kind = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        if target.suffix == '.html':
            html = body.decode('utf-8')
            if relative == 'photos.html' or relative.startswith('content/photos/'):
                html = html.replace('</head>', '<script src="/_manage/controls.js" defer></script></head>')
            body = html.encode('utf-8')
            kind = 'text/html; charset=utf-8'
        return self.send(200, body, kind, session=target.suffix=='.html')

    def do_POST(self):
        if not self.authenticated(write=True):
            return self.send(403, {'error':'管理会话已失效，请从本机管理入口重新打开。'})
        if self.path != '/_manage/cover':
            return self.send(404, {'error':'Not found'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send(415, {'error':'请求格式无效。'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 4096:
                return self.send(413, {'error':'请求大小无效。'})
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(data, dict) or set(data) != {'album','file'}:
                raise ValueError('请求格式无效。')
            validate_choice(self.server.root, data['album'], data['file'])
        except (ValueError, TypeError, UnicodeDecodeError):
            return self.send(422, {'error':'请选择本图册中有效的照片。'})
        if not self.server.publish_lock.acquire(blocking=False):
            return self.send(409, {'error':'正在发布另一项封面更改，请稍候。'})
        try:
            result = self.server.publisher.publish(data['album'], data['file'])
            self.send(200, {'ok':True, **result})
        except PublishError as error:
            self.send(409 if error.step=='check' else 502, {'error':str(error), 'step':error.step})
        except (ValueError, OSError):
            self.send(422, {'error':'封面配置无法保存，请检查本机工作区。'})
        finally:
            self.server.publish_lock.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4180)
    args = parser.parse_args()
    server = ManagerServer(('127.0.0.1', args.port), Path(__file__).resolve().parents[1])
    print(f'Cover manager: http://127.0.0.1:{server.server_port}/photos.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
