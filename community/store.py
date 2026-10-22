"""Reader accounts and comments. No dependency on the owner/admin database."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import unicodedata

SESSION_SECONDS = 8 * 3600
HASH_SLOTS = threading.BoundedSemaphore(2)


class Problem(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def csrf(token):
    return hmac.new(token.encode(), b'forest-reader-csrf-v1', hashlib.sha256).hexdigest()


def password_hash(password, salt):
    if not HASH_SLOTS.acquire(blocking=False):
        raise Problem(429, '请求较多，请稍后重试。')
    try:
        return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**17, r=8, p=1,
                              dklen=64, maxmem=256 * 1024 * 1024)
    finally:
        HASH_SLOTS.release()


class Store:
    def __init__(self, path, articles):
        self.path, self.articles = Path(path), frozenset(articles)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
                    canonical TEXT NOT NULL UNIQUE, salt BLOB NOT NULL, hash BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, article TEXT NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id), text TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS comments_article ON comments(article,id);
                CREATE TABLE IF NOT EXISTS events (action TEXT NOT NULL, subject TEXT NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS events_lookup ON events(action,subject,created);
            ''')
        if os.name == 'posix':
            os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                yield db
        finally:
            db.close()

    def _limits(self, db, rules):
        now = time.time()
        db.execute('DELETE FROM events WHERE created < ?', (now - 3600,))
        db.execute('DELETE FROM sessions WHERE expires <= ?', (now,))
        for action, subject, seconds, maximum in rules:
            count = db.execute('SELECT COUNT(*) FROM events WHERE action=? AND subject=? AND created>?',
                               (action, subject, now - seconds)).fetchone()[0]
            if count >= maximum:
                raise Problem(429, '操作频繁，请稍后再试。评论间隔至少 30 秒。' if action.startswith('comment') else '尝试过多，请稍后再试。')
        for action, subject, _, _ in rules:
            db.execute('INSERT INTO events VALUES (?,?,?)', (action, subject, now))

    def _attempt(self, action, ip, seconds, per_ip, total):
        with self.db() as db:
            self._limits(db, [(action, digest(ip), seconds, per_ip), (action, '*', seconds, total)])

    def register(self, username, password, ip):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,32}', username):
            raise Problem(422, '用户名需为 3–32 位字母、数字、点、下划线或短横线。')
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise Problem(422, '密码需为 12–128 个字符。')
        try:
            password.encode('utf-8')
        except UnicodeError:
            raise Problem(422, '密码包含无效字符。') from None
        self._attempt('register', ip, 3600, 5, 50)
        with self.db() as db:
            if db.execute('SELECT 1 FROM users WHERE canonical=?', (username.lower(),)).fetchone():
                raise Problem(409, '该用户名已被使用。')
        salt = secrets.token_bytes(32)
        hashed = password_hash(password, salt)
        token = secrets.token_urlsafe(32)
        try:
            with self.db() as db:
                user_id = db.execute('INSERT INTO users(username,canonical,salt,hash) VALUES (?,?,?,?)',
                                     (username, username.lower(), salt, hashed)).lastrowid
                self._new_session(db, user_id, token)
        except sqlite3.IntegrityError:
            raise Problem(409, '该用户名已被使用。') from None
        return token

    def _new_session(self, db, user_id, token):
        db.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
        db.execute('DELETE FROM sessions WHERE hash IN (SELECT hash FROM sessions WHERE user_id=? ORDER BY expires DESC LIMIT -1 OFFSET 7)', (user_id,))
        db.execute('INSERT INTO sessions VALUES (?,?,?)', (digest(token), user_id, time.time() + SESSION_SECONDS))

    def login(self, username, password, ip):
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 128 or len(password) > 128:
            raise Problem(401, '用户名或密码不正确。')
        try:
            password.encode('utf-8')
        except UnicodeError:
            raise Problem(401, '用户名或密码不正确。') from None
        self._attempt('login', ip, 900, 10, 60)
        with self.db() as db:
            user = db.execute('SELECT * FROM users WHERE canonical=?', (username.lower(),)).fetchone()
        hashed = password_hash(password, user['salt'] if user else b'forest-reader-unknown-account-v1')
        if not user or not hmac.compare_digest(hashed, user['hash']):
            raise Problem(401, '用户名或密码不正确。')
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            self._new_session(db, user['id'], token)
        return token

    def session(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return None
        with self.db() as db:
            row = db.execute('SELECT u.id,u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.hash=? AND s.expires>?',
                             (digest(token), time.time())).fetchone()
        return dict(row) if row else None

    def logout(self, token):
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE hash=?', (digest(token),))

    def _article(self, article):
        if not isinstance(article, str) or article not in self.articles:
            raise Problem(404, '文章不存在。')

    def post(self, article, text, user, ip):
        if not user:
            raise Problem(401, '请先登录。')
        self._article(article)
        if not isinstance(text, str):
            raise Problem(422, '评论需为 1–100 字。')
        text = unicodedata.normalize('NFC', text).strip()
        if not 1 <= len(text) <= 100 or any(unicodedata.category(c) in ('Cs', 'Cc') and c not in '\n\t' for c in text):
            raise Problem(422, '评论需为 1–100 字，且不能包含控制字符。')
        now = time.time()
        with self.db() as db:
            self._limits(db, [('comment-user', str(user['id']), 30, 1), ('comment-ip', digest(ip), 3600, 20)])
            item_id = db.execute('INSERT INTO comments(article,user_id,text,created) VALUES (?,?,?,?)',
                                 (article, user['id'], text, now)).lastrowid
        return self._item({'id': item_id, 'text': text, 'created': now, 'username': user['username'], 'user_id': user['id']}, user)

    @staticmethod
    def _item(row, user):
        return {'id': row['id'], 'text': row['text'], 'author': row['username'],
                'created': datetime.fromtimestamp(row['created'], timezone.utc).isoformat().replace('+00:00', 'Z'),
                'mine': bool(user and row['user_id'] == user['id'])}

    def list(self, article, user=None, before=None):
        self._article(article)
        if before is not None and (type(before) is not int or not 0 < before < 2**63):
            raise Problem(422, '分页参数无效。')
        with self.db() as db:
            rows = db.execute('SELECT c.*,u.username FROM comments c JOIN users u ON u.id=c.user_id WHERE c.article=? AND c.id<? ORDER BY c.id DESC LIMIT 21',
                              (article, before or 2**63 - 1)).fetchall()
        return {'comments': [self._item(row, user) for row in rows[:20]], 'next': rows[19]['id'] if len(rows) > 20 else None}

    def delete(self, item_id, user):
        if not user:
            raise Problem(401, '请先登录。')
        with self.db() as db:
            row = db.execute('SELECT user_id FROM comments WHERE id=?', (item_id,)).fetchone()
            if not row:
                raise Problem(404, '评论已不存在。')
            if row['user_id'] != user['id']:
                raise Problem(403, '只能删除自己的评论。')
            db.execute('DELETE FROM comments WHERE id=?', (item_id,))
