# Article Comments Implementation Plan

> Execute inline using executing-plans. Review the completed feature using requesting-code-review before integration.

**Goal:** Independent reader accounts and authenticated comments of at most 100 Unicode code points on every essay, fully working locally, GitHub managed, deployment deferred.

**Architecture:** Same-origin Python loopback API + SQLite, separate from cover admin. Static comment UI defaults disabled; local preview enables it without changing the checked-in deployment flag.

**Tech Stack:** Python standard library, SQLite, scrypt, native browser dialog/fetch, existing CSS variables, unittest and Playwright.

## Task 1 — Store and authentication

- [x] Write `community/test_store.py` using temporary databases. Test `Store.register(username,password,ip)`, `login`, `session`, `logout`, `post(article,text,user,ip)`, `list(article,user,before)`, `delete(id,user)`; rejection uses `Problem(status,message)`.
- [x] Run `python -m unittest discover -s community -p test_store.py -v`; first assertion checks that `community/store.py` exists, demonstrating missing functionality.
- [x] Implement `community/store.py` with bounded scrypt, SHA256 session hashes, UTC timestamps, SQL parameters, persistent rate events, limits and article allowlist loaded by server.
- [x] Re-run store tests to green, including restarted Store instances.

## Task 2 — HTTP and local preview

- [x] Write `community/test_server.py`: real HTTP connections to ephemeral loopback server and temp SQLite; assert authentication, JSON/Origin/Host/CSRF, body limits, inaccessible scripts/DB and production origin constraints.
- [x] Run tests first to see missing `community/server.py` failure.
- [x] Implement `community/server.py`, `community/articles.json`, `community/start.ps1`. Routes: GET session/comments/health; POST register/login/logout/comments/comments/<id>/delete. Static preview uses a resolved-file whitelist.
- [x] Run all community tests to green.

## Task 3 — Frontend

- [x] Add browser test `community/test_browser.cjs` against an isolated real server/database, verifying two accounts, article isolation, length counter, password dialog, deletion permissions, XSS safety, theme/mobile and disabled static mode.
- [x] Run before UI exists and confirm absent comment section failure.
- [x] Add `assets/comments.js`, `assets/comments.css`, `assets/comments-config.js`. Insert semantic section and script/style references in both essay HTML files. Use only DOM textContent for user data; keep all credentials/CSRF in memory or HttpOnly cookies.
- [x] Run browser test and inspect screenshots; refine only scoped UI issues.

## Task 4 — Delivery

- [x] Document local start/stop, counting rule, account/password recovery limits, persistent data, backups, future same-origin HTTPS proxy and explicit deferred deployment in `community/README.md` and root README.
- [x] Run community, existing manager/privacy and remote_admin tests, JS syntax, git diff --check, browser QA.
- [x] Request independent code/security review, resolve important findings, rerun affected checks.
- [ ] Commit scoped files, fast-forward main, push GitHub, verify remote SHA and Pages workflow where available. Do not open public websites, deploy Tencent or touch DNS.
