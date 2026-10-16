#!/usr/bin/env python3
"""Install a static Git archive and atomically switch the served release."""
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile

BASE = Path('/var/www/chenforest')
INCOMING = Path('/home/ubuntu/site-deploy/incoming')
PAGES = {'index.html', 'photos.html', 'writing.html', 'reading.html', 'projects.html'}
REQUIRED = PAGES | {'assets/site.css', 'assets/theme.css', 'assets/site.js',
                    'content/photos/index.json', 'content/writing/index.json'}
SHA = re.compile(r'[0-9a-f]{40}')


def release_target(link):
    if not link.is_symlink():
        return None
    target = os.readlink(link)
    if not re.fullmatch(r'releases/[0-9a-f]{40}', target):
        raise ValueError('Unexpected release link')
    path = BASE / target
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Release directory missing or invalid')
    return target


def switch(target):
    current = release_target(BASE / 'current')
    if current == target:
        return
    if current:
        previous = BASE / '.previous-next'
        previous.unlink(missing_ok=True)
        previous.symlink_to(current)
        previous.replace(BASE / 'previous')
    pending = BASE / '.current-next'
    pending.unlink(missing_ok=True)
    pending.symlink_to(target)
    pending.replace(BASE / 'current')


def install(revision):
    if not SHA.fullmatch(revision):
        raise ValueError('Expected a full Git commit SHA')
    archive = INCOMING / (revision + '.tar')
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Archive must be a regular incoming file')
    if archive.stat().st_size > 200 * 1024 * 1024:
        raise ValueError('Archive exceeds 200 MiB')
    destination = BASE / 'releases' / revision
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=BASE / 'releases'))
    staging.chmod(0o755)
    try:
        with tarfile.open(archive, 'r:') as bundle:
            if bundle.pax_headers.get('comment') != revision:
                raise ValueError('Git archive revision does not match')
            members = bundle.getmembers()
            if len(members) > 10000 or sum(m.size for m in members) > 200 * 1024 * 1024:
                raise ValueError('Archive exceeds static site limits')
            seen = set()
            for member in members:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or '\\' in member.name or
                        any(p.startswith('.') for p in path.parts) or
                        not path.parts or
                        not (member.name in PAGES or path.parts[0] in {'assets', 'content'}) or
                        member.name in seen or not (member.isdir() or member.isfile())):
                    raise ValueError('Unexpected archive member: ' + member.name)
                seen.add(member.name)
                output = staging.joinpath(*path.parts)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True, mode=0o755)
                else:
                    if member.size > 25 * 1024 * 1024:
                        raise ValueError('Individual file exceeds 25 MiB')
                    output.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    with bundle.extractfile(member) as source, output.open('xb') as target:
                        shutil.copyfileobj(source, target)
                    output.chmod(0o644)
        if any(not (staging / name).is_file() for name in REQUIRED):
            raise ValueError('Required site files missing')
        for kind in ('photos', 'writing'):
            if not isinstance(json.loads((staging / 'content' / kind / 'index.json').read_text()), list):
                raise ValueError('Content index must be a JSON array')
        (staging / '.release-revision').write_text(revision + '\n')
        (staging / '.release-revision').chmod(0o644)
        if destination.exists() or destination.is_symlink():
            if (destination.is_symlink() or
                    (destination / '.release-revision').read_text().strip() != revision):
                raise ValueError('Existing release is invalid')
        else:
            staging.rename(destination)
        switch('releases/' + revision)
        print('ACTIVE ' + revision)
    finally:
        # Only this invocation's private staging directory can be removed.
        if staging.exists():
            shutil.rmtree(staging)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo')
    if len(sys.argv) != 2:
        raise SystemExit('Usage: chenforest-activate <commit-sha|--rollback>')
    BASE.mkdir(mode=0o755, parents=True, exist_ok=True)
    (BASE / 'releases').mkdir(mode=0o755, exist_ok=True)
    with (BASE / '.deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if sys.argv[1] == '--rollback':
            target = release_target(BASE / 'previous')
            if not target:
                raise SystemExit('No previous release available')
            switch(target)
            print('ROLLED BACK ' + target)
        else:
            install(sys.argv[1])


if __name__ == '__main__':
    main()
