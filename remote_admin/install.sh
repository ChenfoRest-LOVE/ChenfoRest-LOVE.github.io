#!/bin/sh
# Run from an uploaded repository archive as root. No passwords or Git credentials.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run with sudo.' >&2; exit 1; }
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test -f "$src/../manage/catalog.py"
test -f "$src/../deploy/nginx.conf"
test -r /var/www/chenforest/current/content/photos/albums.json
command -v python3 >/dev/null
if ! id forest-admin >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/forest-admin --shell /usr/sbin/nologin forest-admin
fi
install -d -o root -g root -m 755 /opt/forest-admin
install -d -o forest-admin -g forest-admin -m 700 /var/lib/forest-admin
install -d -m 700 /var/backups/chenforest
stamp=$(date +%Y%m%dT%H%M%S)
if [ -f /opt/forest-admin/server.py ]; then
    tar -czf "/var/backups/chenforest/admin-code-before-$stamp.tar.gz" -C /opt forest-admin
fi
if [ -f /etc/systemd/system/forest-admin.service ]; then
    cp -p /etc/systemd/system/forest-admin.service "/var/backups/chenforest/admin-unit-before-$stamp.service"
fi
for file in server.py admin.html admin.css admin.js setup.html setup.js; do
    install -o root -g root -m 644 "$src/$file" "/opt/forest-admin/$file"
done
install -o root -g root -m 644 "$src/../manage/catalog.py" /opt/forest-admin/catalog.py
install -o root -g root -m 644 "$src/forest-admin.service" /etc/systemd/system/forest-admin.service
backup="/var/backups/chenforest/nginx-before-admin-$stamp.conf"
cp -p /etc/nginx/sites-available/chenforest "$backup"
install -o root -g root -m 644 "$src/../deploy/nginx.conf" /etc/nginx/sites-available/chenforest
if ! nginx -t; then
    cp -p "$backup" /etc/nginx/sites-available/chenforest
    echo 'Nginx configuration restored; install stopped.' >&2
    exit 1
fi
systemctl daemon-reload
systemctl enable --now forest-admin.service
systemctl restart forest-admin.service
sleep 1
if ! systemctl is-active --quiet forest-admin.service; then
    cp -p "$backup" /etc/nginx/sites-available/chenforest
    echo 'Admin service did not start; Nginx configuration restored.' >&2
    exit 1
fi
systemctl reload nginx
echo 'Forest admin installed; account setup is SSH-only.'
