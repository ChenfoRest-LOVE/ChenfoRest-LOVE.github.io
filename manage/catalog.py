"""Render public album covers from version-controlled metadata."""
from html import escape
import json
from pathlib import Path
import re
import tempfile

ALBUMS = 'content/photos/albums.json'
PHOTO_INDEX = 'content/photos/index.json'
DIRECTORY = re.compile(r'(<section class="album-directory"[^>]*>).*?(</section>)', re.S)


def read_catalog(root):
    albums = json.loads((root / ALBUMS).read_text(encoding='utf-8'))
    photos = json.loads((root / PHOTO_INDEX).read_text(encoding='utf-8'))
    if not isinstance(albums, list) or not isinstance(photos, list):
        raise ValueError('图册配置格式无效。')
    ids = set()
    for album in albums:
        if (not isinstance(album, dict) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', album.get('id', ''))
                or album['id'] in ids or not all(isinstance(album.get(k), str) for k in ['title', 'english', 'cover'])):
            raise ValueError('图册配置格式无效。')
        ids.add(album['id'])
    return albums, photos


def validate_choice(root, album, file):
    if not isinstance(album, str) or not isinstance(file, str):
        raise ValueError('请选择本图册中的照片。')
    albums, photos = read_catalog(root)
    if not any(a['id'] == album for a in albums):
        raise ValueError('图册不存在。')
    matches = [p for p in photos if p.get('category') == album and p.get('file') == file]
    if len(matches) != 1 or not re.fullmatch(r'images/[a-z0-9-]+\.(?:webp|jpg|jpeg|png)', file):
        raise ValueError('只能选择本图册中的照片。')
    return albums, photos


def render_directory(albums, photos):
    entries = []
    for number, album in enumerate(albums):
        selected = [p for p in photos if p.get('category') == album['id']]
        matches = [p for p in selected if p.get('file') == album['cover']]
        if len(matches) != 1:
            raise ValueError('封面照片不属于对应图册。')
        photo = matches[0]
        thumbnail = photo.get('thumbnail', photo['file'])
        if not re.fullmatch(r'images/[a-z0-9-]+\.(?:webp|jpg|jpeg|png)', thumbnail):
            raise ValueError('预览图路径无效。')
        width, height = int(photo['width']), int(photo['height'])
        if not 0 < width <= 20000 or not 0 < height <= 20000:
            raise ValueError('照片尺寸无效。')
        entries.append(f'''<a class="album-link" data-album="{album['id']}" href="content/photos/{album['id']}.html"><figure>
<div class="album-cover"><img src="content/photos/{thumbnail}" alt="{escape(photo['alt'], quote=True)}" width="{width}" height="{height}" loading="{'eager' if number < 2 else 'lazy'}" decoding="async" /></div>
<figcaption><div><h2>{escape(album['title'])}</h2><span class="album-english">{escape(album['english'])}</span></div><span class="album-count">{len(selected):02d} 张<span aria-hidden="true">↗</span></span></figcaption>
</figure></a>''')
    return '\n'.join(entries)


def atomic_write(path, text):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, prefix='.cover-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def set_cover(root, album, file):
    albums, photos = validate_choice(root, album, file)
    changed = False
    for entry in albums:
        if entry['id'] == album:
            changed = entry['cover'] != file
            entry['cover'] = file
    html_path = root / 'photos.html'
    previous_html = html_path.read_text(encoding='utf-8')
    if len(DIRECTORY.findall(previous_html)) != 1:
        raise ValueError('图册目录结构已变化，无法安全更新封面。')
    html = DIRECTORY.sub(lambda match: match[1] + render_directory(albums, photos) + match[2], previous_html, count=1)
    # Also repair a static cover that is inconsistent with the chosen metadata.
    changed = changed or html != previous_html
    if not changed:
        return False
    config = root / ALBUMS
    previous_config = config.read_text(encoding='utf-8')
    try:
        atomic_write(config, json.dumps(albums, ensure_ascii=False, indent=2) + '\n')
        atomic_write(html_path, html)
    except OSError:
        atomic_write(config, previous_config)
        atomic_write(html_path, previous_html)
        raise
    return True


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    albums, _ = read_catalog(root)
    print('Updated' if set_cover(root, albums[0]['id'], albums[0]['cover']) else 'Already current')
