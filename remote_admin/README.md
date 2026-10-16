# 网站封面管理

管理入口：`https://denss.asia/admin/`。在影像目录页底部点击「管理」，使用自己的管理员账号和密码登录，选择图册中的照片并点击「设为封面」。保存后，访客下次打开影像目录时会读取新封面，无需启动本机管理服务。

GitHub 管理网站与后台代码；封面选择保存在腾讯云的 SQLite 数据库中，不需要每次生成 Git 提交，也不向服务器提供 GitHub 写入凭据。GitHub Pages 与腾讯云网站读取同一个公开的只读封面 API。API 暂时不可达、访客禁用 JavaScript 时，目录展示仓库中的默认封面。

注意：2026-10-16 观察到腾讯云对未备案域名的拦截。域名 HTTPS 恢复之前，公网登录和 GitHub Pages 的动态封面读取可能不可用；已有静态封面仍可在 GitHub Pages 浏览。不能将服务器内部测试视为公网访问已恢复。

## 首次设置账号

只需一次，通过现有 SSH 密钥打开本机到服务器的加密转发：

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:4190:127.0.0.1:6191 xmu-server
```

打开 `http://127.0.0.1:4190/`，自行设置账号和密码。密码至少 14 位，建议交由密码管理器生成和保存；不要在聊天、命令参数或项目文件中填写密码。虽然浏览器显示本机 HTTP，发往服务器的流量在 SSH 通道内加密。

设置成功后，初始化入口返回 410，不允许再创建账号；服务重启后不再监听初始化端口。关闭 SSH 转发即可。日后直接在 HTTPS 管理页登录，不需要 SSH 或本机服务。

## 服务和数据

- `forest-admin.service`：非特权专用用户 `forest-admin`，开机启动。
- 代码：`/opt/forest-admin/`，root 所有；仅使用系统 Python 标准库。
- 数据：`/var/lib/forest-admin/admin.sqlite`，目录 700、数据库 600。
- 管理监听：`127.0.0.1:6190`，Nginx 仅在域名 HTTPS 代理 `/admin/`、`/api/admin/` 和 `/api/covers`。
- 首次设置：`127.0.0.1:6191`，不经过 Nginx，不对公网开放。
- 密码使用 scrypt 哈希；会话仅保存哈希，8 小时过期，退出会撤销。写入校验会话、来源和 CSRF，并只允许该图册内已收录的照片。
- 登录失败限制：单 IP 每 15 分钟 5 次，全局 30 次；最多同时执行两个密码计算。
- 服务不会读取签到程序配置、私钥或 GitHub 凭据，不发送通知、不增加同步定时任务。

检查：`ssh xmu-server 'systemctl is-active forest-admin; systemctl is-enabled forest-admin'`。

## 部署与更新

静态网页继续使用 `deploy/publish.ps1`。后台更新需要额外上传 `remote_admin/`、`manage/catalog.py` 与 `deploy/nginx.conf`，然后在上传的目录运行 `sudo sh remote_admin/install.sh`。安装脚本备份原 Nginx 配置并检查语法，保留已有数据库与账号；不要将数据库打包到静态目录或 Git 仓库。

服务文件由 root 安装，只允许写入自己的数据目录。HTTP 的 IP 访问和本机 `/__revision` 发布检查保持原样。公网管理必须使用有效 HTTPS，不能通过普通 HTTP 提交密码。

## 备份与账号恢复

数据库含密码哈希与会话哈希，备份应留在服务器受保护目录：维护前用 `sudo systemctl stop forest-admin`，将数据库以 600 权限复制到 root 所有的 `/var/backups/forest-admin/`，再启动服务。备份不要提交 GitHub。

忘记密码时，使用现有 SSH 管理权限：停止后台、备份数据库，通过 Python/SQLite 只删除 `admin` 和 `sessions` 表内记录（保留 `covers` 表），重启后台，再使用上述一次性 SSH 设置页创建管理员。此操作会撤销所有会话，应仅由服务器所有者执行。

旧的 `manage/start.ps1` 仍用于维护**仓库默认封面**。在线后台已为某相册保存选择后，该选择优先于仓库默认值；日常更换封面请使用在线管理页。

## 验证

```powershell
python -m unittest discover -s remote_admin -p test_admin.py -v
```

测试覆盖单管理员、密码哈希、会话过期/退出、限速持久化、并发初始化、Host/Origin/CSRF、照片归属、只读 CORS、初始化仅回环开放、封面数据重启保留及照片删除后的默认回退。使用临时数据库，不写真实账号或发布网站。
