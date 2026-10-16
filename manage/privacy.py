"""Prepare authenticated album encryption without persisting a password."""
import base64
from html import escape
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile

from catalog import ALBUMS, PHOTO_INDEX, DIRECTORY, read_catalog, render_directory

ITERATIONS = 600000
MAX_RAW = 24 * 1024 * 1024
IMAGE = re.compile(r'images/[a-z0-9-]+\.(?:webp|jpg|jpeg|png)')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def check_password(password):
    if not isinstance(password, str) or not 14 <= len(password) <= 128 or len(set(password)) < 6:
        raise ValueError('密码需为 14–128 位，至少包含 6 种不同字符。请保存好密码，无法找回。')


def encrypt_payload(payload, password, album):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    check_password(password)
    salt, iv = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS, dklen=32)
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    if len(raw) > MAX_RAW * 1.5:
        raise ValueError('单册图片总大小超过 24 MiB，请先压缩或拆分图册。')
    cipher = AESGCM(key).encrypt(iv, raw, ('forest-album-v1:' + album).encode())
    return {'format': 'forest-album-v1', 'album': album, 'iterations': ITERATIONS,
            'salt': base64.b64encode(salt).decode(), 'iv': base64.b64encode(iv).decode(),
            'ciphertext': base64.b64encode(cipher).decode()}


def decrypt_payload(envelope, password, album):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        if not isinstance(password, str) or not 1 <= len(password) <= 128:
            raise ValueError()
        if envelope['format'] != 'forest-album-v1' or envelope['album'] != album or envelope['iterations'] != ITERATIONS:
            raise ValueError()
        salt = base64.b64decode(envelope['salt'], validate=True)
        iv = base64.b64decode(envelope['iv'], validate=True)
        cipher = base64.b64decode(envelope['ciphertext'], validate=True)
        if len(salt) != 16 or len(iv) != 12 or not 16 <= len(cipher) <= MAX_RAW * 1.6:
            raise ValueError()
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS, dklen=32)
        raw = AESGCM(key).decrypt(iv, cipher, ('forest-album-v1:' + album).encode())
        payload = json.loads(raw)
        if payload['album']['id'] != album or not isinstance(payload['page'], str):
            raise ValueError()
        validate_private_photos(payload['photos'], payload['files'], album)
        return payload
    except Exception:
        raise ValueError('密码不正确，或加密文件已损坏。') from None


def validate_private_photos(photos, files, album):
    if not isinstance(photos, list) or not photos or not isinstance(files, dict):
        raise ValueError('图册内容无效。')
    expected = set()
    for photo in photos:
        if not isinstance(photo, dict) or photo.get('category') != album or not all(isinstance(photo.get(k), str) for k in ['alt', 'caption', 'file', 'thumbnail']):
            raise ValueError('图册照片信息无效。')
        if any(not IMAGE.fullmatch(photo[k]) for k in ['file', 'thumbnail']):
            raise ValueError('图册图片路径无效。')
        if not all(type(photo.get(k)) is int and 0 < photo[k] <= 20000 for k in ['width', 'height']):
            raise ValueError('图册图片尺寸无效。')
        expected.update([photo['file'], photo['thumbnail']])
    if expected != set(files) or len({p['file'] for p in photos}) != len(photos):
        raise ValueError('图册文件清单无效。')


def locked_page(page, album):
    slug = album['id']
    section = f'''<section class="module-content" aria-labelledby="module-title">
<div class="album-lock" id="album-lock"><div class="lock-glyph" aria-hidden="true"><svg viewBox="0 0 24 24" width="24" height="24"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg></div><p class="section-label">PRIVATE ARCHIVE</p><h2>密码保护</h2><p class="lock-description">输入相册密码，查看影像。</p><form id="album-password-form"><label for="album-password">相册密码</label><div class="album-password-row"><input id="album-password" name="password" type="password" autocomplete="current-password" maxlength="128" required disabled /><button type="submit" disabled>解锁相册 <span aria-hidden="true">↗</span></button></div></form><p id="album-lock-status" role="status" aria-live="polite"></p><noscript><p>此相册需要启用 JavaScript 才能解锁。</p></noscript></div>
<div class="gallery-toolbar" id="private-toolbar" hidden><p id="photo-note">{album['count']:02d} 张影像</p><div class="photo-filters" role="group" aria-label="筛选影像" hidden></div><button class="album-relock" id="album-relock" type="button">重新锁定</button></div>
<p id="photo-status" class="content-status" role="status" hidden></p><div id="photo-grid" class="photo-grid album-gallery" data-album="{slug}" data-protected="true" data-payload="private/{slug}.enc.json" hidden></div></section>'''
    pattern = re.compile(r'<section class="module-content".*?</section>', re.S)
    if len(pattern.findall(page)) != 1:
        raise ValueError('相册页面结构已变化，无法安全设置密码。')
    page = pattern.sub(lambda _: section, page, count=1)
    return page.replace('</head>', '<script src="../../assets/album-lock.js?v=20261016-private" defer></script></head>')


def blurred_cover(raw):
    from PIL import Image, ImageFilter, ImageOps
    with Image.open(BytesIO(raw)) as source:
        image = ImageOps.fit(source.convert('RGB'), (32, 24)).filter(ImageFilter.GaussianBlur(4)).resize((384, 288))
    output = BytesIO()
    image.save(output, format='WEBP', quality=65)
    return output.getvalue()


def plan_privacy(root, album_id, action, password, new_password=None):
    root = Path(root).resolve()
    albums, photos = read_catalog(root)
    album = next((a for a in albums if a['id'] == album_id), None)
    if not album or action not in ['lock', 'password', 'unlock']:
        raise ValueError('相册或操作不存在。')
    private = f'content/photos/private/{album_id}.enc.json'
    preview = f'content/photos/images/{album_id}-locked.webp'
    page_path = f'content/photos/{album_id}.html'
    changes = {}
    if action == 'lock':
        if album.get('protected'):
            raise ValueError('相册已设置密码。推送未完成时请使用“重试推送”。')
        check_password(password)
        selected = [p for p in photos if p['category'] == album_id]
        files = {name: None for p in selected for name in [p['file'], p.get('thumbnail', p['file'])]}
        validate_private_photos(selected, files, album_id)
        if any(p.get(k) in files for p in photos if p['category'] != album_id for k in ['file', 'thumbnail']):
            raise ValueError('照片文件同时被其他相册引用，请先拆分文件。')
        total = 0
        for name in files:
            path = root / 'content/photos' / name
            if path.is_symlink() or not path.resolve().is_relative_to(root / 'content/photos/images'):
                raise ValueError('图片文件路径无效。')
            raw = path.read_bytes()
            total += len(raw)
            if total > MAX_RAW:
                raise ValueError('单册图片总大小超过 24 MiB，请先压缩或拆分图册。')
            files[name] = base64.b64encode(raw).decode()
            changes['content/photos/' + name] = None
        original_page = (root / page_path).read_bytes().decode('utf-8')
        payload = {'album': dict(album), 'photos': selected, 'files': files, 'page': original_page}
        changes[private] = json_bytes(encrypt_payload(payload, password, album_id))
        cover = next(p for p in selected if p['file'] == album['cover'])
        changes[preview] = blurred_cover(base64.b64decode(files[cover['thumbnail']]))
        album.update({'protected': True, 'count': len(selected), 'payload': f'private/{album_id}.enc.json', 'cover': f'images/{album_id}-locked.webp'})
        changes[page_path] = locked_page(original_page, album).encode()
        photos = [p for p in photos if p['category'] != album_id]
    else:
        if not album.get('protected'):
            raise ValueError('相册尚未设置密码。')
        encrypted = json.loads((root / private).read_text(encoding='utf-8'))
        payload = decrypt_payload(encrypted, password, album_id)
        if action == 'password':
            changes[private] = json_bytes(encrypt_payload(payload, new_password, album_id))
            return changes
        for name, data in payload['files'].items():
            target = 'content/photos/' + name
            if (root / target).exists():
                raise ValueError('还原图片路径已存在，请先检查文件冲突。')
            changes[target] = base64.b64decode(data, validate=True)
        # Group by the stable album catalog, retaining the order within each album.
        # Stored global offsets become stale when another album is locked independently.
        photos.extend(payload['photos'])
        order = {entry['id']: i for i, entry in enumerate(albums)}
        photos.sort(key=lambda photo: order.get(photo['category'], len(order)))
        album.clear()
        album.update(payload['album'])
        changes[page_path] = payload['page'].encode()
        changes[private] = None
        changes[preview] = None
    changes[ALBUMS] = json_bytes(albums)
    changes[PHOTO_INDEX] = json_bytes(photos)
    html = (root / 'photos.html').read_text(encoding='utf-8')
    if len(DIRECTORY.findall(html)) != 1:
        raise ValueError('图册目录结构已变化。')
    changes['photos.html'] = DIRECTORY.sub(lambda match: match[1] + render_directory(albums, photos) + match[2], html, count=1).encode()
    return changes


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.privacy-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def apply_changes(root, changes):
    root = Path(root).resolve()
    before = {}
    for name in changes:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('变更路径无效。')
        before[name] = path.read_bytes() if path.exists() else None
    def write(items):
        for name, data in items.items():
            if data is None:
                (root / name).unlink(missing_ok=True)
            else:
                atomic_bytes(root / name, data)
    try:
        write(changes)
    except OSError:
        write(before)
        raise
