# 文章评论（本地可用，公网待上线）

文章正文下方均有评论区，沿用现有深浅主题。访客可阅读，独立账号注册/登录后可发布 1–100 字的纯文本评论；支持退出、删除自己的评论，以及每页 20 条的“更早的评论”。账号不具备封面管理员权限，两套数据库完全独立。

## 本地使用

在仓库根目录运行：

```powershell
./community/start.ps1
```

打开 `http://127.0.0.1:4192/writing.html`，进入文章后点击“登录 → 创建账号”，自行设置用户名和密码。不要将密码发到聊天或提交到仓库。预览仅监听本机，不需要启动旧的 4180 封面管理服务。再次执行脚本会重启这个预览服务并保留数据。

停止：

```powershell
./community/start.ps1 -Stop
```

需要 Python 3.10+，仅使用标准库，启动脚本优先使用本机已有 Codex Python runtime，找不到时使用 PATH 中的 Python。也可直接执行 `python community/server.py --port 4192`。

Windows 数据在 `%LOCALAPPDATA%/ForestComments/community.sqlite`；Linux 默认在 `${XDG_STATE_HOME:-~/.local/state}/forest-comments/community.sqlite`。可使用 `--data /absolute/private/path/community.sqlite` 指定。数据库必须位于网站仓库之外；包含账号哈希、会话哈希和评论，不能提交 Git 或放入网站静态目录。停止预览服务后复制该文件即可备份；恢复前也先停止服务。

## 规则

- 用户名 3–32 位，仅字母、数字、点、下划线和短横线，大小写不敏感；密码 12–128 个 Unicode 码点。密码通过随机 salt 的 scrypt 保存，后台没有明文密码。当前不收集邮箱，也不提供在线密码找回；这是本地第一版的明确范围。
- 评论先 NFC 规范化并去掉首尾空白，再按 Unicode 码点计数。汉字、标点、内部空格和换行都计数；普通单码点 emoji 算 1，多码点组合 emoji 按所含码点数计。前后端独立校验，禁止空白评论、控制字符与超过 100 字的内容。
- 同一账号每 30 秒最多一条评论，同一 IP 每小时最多 20 条。限速跨文章生效，删除评论不会绕过限速。注册每 IP 每小时最多 5 次尝试、全局 50 次；登录每 IP 每 15 分钟最多 10 次尝试、全局 60 次，重启服务不清空限速。
- 会话有效期 8 小时，Cookie 为 HttpOnly、SameSite=Strict；生产额外强制 Secure。会话和 CSRF 值不写入 localStorage/sessionStorage。写操作验证来源、会话和 CSRF。最多同时 24 个连接、2 个密码哈希任务，请求体最多 4096 字节。
- 失败保留评论草稿；刷新页面会清除尚未提交的草稿。评论公开可见，请勿提交隐私信息。删除只删除当前数据库记录，备份中可能仍有历史数据。

新增文章时在 `articles.json` 添加 ID 与 HTML 路径，并复用现有文章的评论 section、两个脚本和样式引用，`data-comments-article` 使用同一个 ID。

## GitHub 与后续部署

本次只维护代码和本地预览，未向腾讯云同步，也未恢复 DNS。GitHub Pages 的 `assets/comments-config.js` 默认 `enabled: false`，文章下显示“评论暂未开放”，不请求 API；本地预览只在响应中启用配置，不改仓库开关。

备案与 HTTPS 恢复后，建议将后端与网站放在**同一 HTTPS 域名**，不使用跨站 Cookie，不借用封面管理员账号。后续需独立完成：

1. 专用非特权用户、受保护的数据目录、systemd 服务，使用 `--origin https://denss.asia --trust-proxy --port 6192`，仍只监听 `127.0.0.1`。
2. 在现有 HTTPS server 块添加下列代理片段，保留现有 `/admin/` 与 `/api/covers`，先检查 Nginx 配置再重载：

```nginx
location ^~ /api/community/ {
    client_max_body_size 4k;
    proxy_pass http://127.0.0.1:6192;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Origin $http_origin;
    proxy_set_header X-Forwarded-Proto https;
    proxy_connect_timeout 3s;
    proxy_read_timeout 20s;
    proxy_hide_header Access-Control-Allow-Origin;
}

# Only this same-origin site enables comments; GitHub Pages keeps the disabled file.
location = /assets/comments-config.js {
    proxy_pass http://127.0.0.1:6192;
    proxy_set_header Host $host;
}
```

3. 上述精确路径代理会为同源网站启用评论，仓库中的开关继续保持关闭。验收真实注册、登录、发布、删除、限速和备份。`--trust-proxy` 仅用于可信本机反代，缺少合法 X-Real-IP 时写入拒绝；不要把后端端口暴露到公网。

GitHub Pages 与 `denss.asia` 属于不同站点，本版不启用跨站登录；GitHub Pages 继续作为静态预览。将来若要两处均支持在线评论，需另行设计身份接入与安全的跨站流程。

## 验证（不访问公网，不发送通知）

```powershell
python -m unittest discover -s community -p "test_*.py" -v
node community/test_browser.cjs
```

浏览器测试使用现有 Playwright 与 Chrome、独立临时数据库和隔离浏览器，不触碰真实账号或评论；仅访问本机 4194。可通过 `PLAYWRIGHT_MODULE`、`TEST_PYTHON` 指定已有运行时，通过 `COMMENTS_SCREENSHOT` 指定截图路径。测试账号密码是固定测试夹具，不是任何真实凭据。
