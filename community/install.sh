#!/bin/sh
# Install the already-reviewed reader API next to the existing static site.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test -f "$src/server.py"
test -f "$src/store.py"
test -f "$src/articles.json"
test -f "$src/../deploy/nginx.conf"
test -r /var/www/chenforest/current/index.html
test -f /etc/nginx/sites-available/chenforest
command -v python3 >/dev/null
command -v systemd-analyze >/dev/null
python3 -m json.tool "$src/articles.json" >/dev/null
python3 - "$src/server.py" "$src/store.py" <<'PY'
import pathlib, sys
for name in sys.argv[1:]:
    compile(pathlib.Path(name).read_bytes(), name, 'exec')
PY
systemd-analyze verify "$src/forest-comments.service"
if ! id forest-comments >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/forest-comments --shell /usr/sbin/nologin forest-comments
fi
install -d -o root -g root -m 755 /opt/forest-comments
install -d -o forest-comments -g forest-comments -m 700 /var/lib/forest-comments
install -d -o root -g root -m 700 /var/backups/chenforest
stamp=$(date +%Y%m%dT%H%M%S)
backup="/var/backups/chenforest/comments-$stamp"
install -d -o root -g root -m 700 "$backup"
cp -p /etc/nginx/sites-available/chenforest "$backup/nginx.conf"
if [ -f /etc/systemd/system/forest-comments.service ]; then
    cp -p /etc/systemd/system/forest-comments.service "$backup/forest-comments.service"
fi
if [ -f /opt/forest-comments/server.py ]; then
    cp -p /opt/forest-comments/server.py /opt/forest-comments/store.py /opt/forest-comments/articles.json "$backup/"
fi
if [ -f /var/lib/forest-comments/community.sqlite ]; then
    systemctl stop forest-comments.service
    cp -p /var/lib/forest-comments/community.sqlite "$backup/community.sqlite"
    chown root:root "$backup/community.sqlite"
    chmod 600 "$backup/community.sqlite"
fi
for file in server.py store.py articles.json; do
    install -o root -g root -m 644 "$src/$file" "/opt/forest-comments/$file"
done
install -o root -g root -m 644 "$src/forest-comments.service" /etc/systemd/system/forest-comments.service
systemctl daemon-reload
systemctl enable --now forest-comments.service
systemctl restart forest-comments.service
if ! curl --fail --silent --show-error --max-time 5 -H 'Host: denss.asia' http://127.0.0.1:6192/api/community/health >/dev/null; then
    echo 'Reader API failed to start; Nginx was not changed.' >&2
    exit 1
fi
install -o root -g root -m 644 "$src/../deploy/nginx.conf" /etc/nginx/sites-available/chenforest
if ! nginx -t; then
    cp -p "$backup/nginx.conf" /etc/nginx/sites-available/chenforest
    echo 'Nginx configuration restored.' >&2
    exit 1
fi
systemctl reload nginx
if ! curl --fail --silent --show-error --max-time 5 --resolve denss.asia:443:127.0.0.1 https://denss.asia/api/community/health >/dev/null; then
    cp -p "$backup/nginx.conf" /etc/nginx/sites-available/chenforest
    nginx -t && systemctl reload nginx
    echo 'HTTPS reader health check failed; Nginx configuration restored.' >&2
    exit 1
fi
printf 'Reader comments installed; backup: %s\n' "$backup"
