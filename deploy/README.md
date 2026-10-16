# 腾讯云静态部署

当前工作约定：备案期间只修改本地项目并提交 GitHub；腾讯云留待用户后续明确要求再同步。以下脚本保留供届时手动使用，本机封面管理不再调用它。

GitHub `main` 为唯一代码来源。发布脚本在本机获取 `origin/main`，用 `git archive` 只打包五个 HTML、`assets/` 和 `content/`，通过既有 SSH 别名上传。未提交改动、Git 凭据、文档与部署脚本不会进入网站根目录。服务器无需保存 GitHub 写入凭据。

在线封面后台独立部署，账号与封面选择保存在受保护的服务器数据库中；静态发布和回滚均不覆盖该数据库。安装、初始化、备份见 `remote_admin/README.md`。

## 更新网站

先将代码推送到 GitHub `main`，再在本机 PowerShell 运行：

```powershell
./deploy/publish.ps1
```

此命令是手动发布，没有定时轮询。需要本机已配置 `ssh xmu-server` 和专用 SSH 密钥；私钥不属于仓库。

封面管理会使用 `-Revision <完整 Git SHA>` 固定本次发布版本；若获取到的 `origin/main` 已改变，脚本会在上传前停止，避免发布其他版本。常规手动发布不传此参数时，继续发布最新的 `origin/main`。

## 服务结构

- Nginx 通过 `/var/www/chenforest/current` 提供静态文件，开机启动。
- 版本目录：`/var/www/chenforest/releases/<Git SHA>`。
- 上一版链接：`/var/www/chenforest/previous`。
- 激活程序：`/usr/local/sbin/chenforest-activate`，root 所有。
- 接收目录：`/home/ubuntu/site-deploy/incoming`，仅 ubuntu 可访问。
- `http://服务器地址/__revision` 返回正在服务的 Git SHA。
- 已有签到程序、账号配置和任务不参与部署。

回滚到上一版：

```powershell
./deploy/publish.ps1 -Rollback
```

检查服务：`ssh xmu-server 'systemctl is-active nginx'`。日志位于 `/var/log/nginx/chenforest-*.log`，不公开到网页。

## 域名与 HTTPS

域名为 `denss.asia` 和 `www.denss.asia`，A 记录指向腾讯云服务器。Let’s Encrypt 证书覆盖两个域名；证书和私钥只保存在服务器 `/etc/letsencrypt/`，不进入仓库或网站目录。

**当前访问状态（2026-10-16 10:39）：腾讯云已拦截未备案域名。** HTTP 返回 302 至腾讯云备案提示页，HTTPS 握手被中途关闭。服务器内部 HTTPS、静态文章与 IP 测试访问正常；已发布的 GitHub Pages 可用。完成备案后再复查公网域名，早前技术验收通过不代表当前仍可从公网访问。

`nginx.conf` 已启用：域名 HTTP 跳转到 `https://denss.asia`，保留路径与查询参数，IP HTTP 与本机发布检查继续可用。云防火墙已允许来源 `0.0.0.0/0` 的 TCP 443，两个域名的公网 HTTPS、五个页面与主要资源已于 2026-10-16 验收通过。新增或迁移实例时，必须先开放端口并验证公网 HTTPS，再启用 HTTP 跳转；放通方法见[腾讯云防火墙说明](https://cloud.tencent.cn/document/product/1207/136745)。

证书使用 Certbot 的 webroot 模式；验证目录为 `/var/lib/chenforest-acme`。HTTP 的 `/.well-known/acme-challenge/` 保留直接访问，不跳转、不受隐藏文件规则阻挡。`certbot.timer` 负责定期检查续期；`reload-nginx-after-renewal.sh` 安装到 `/etc/letsencrypt/renewal-hooks/deploy/reload-chenforest-nginx`，仅在成功续期后检查配置并重载 Nginx。

```powershell
ssh xmu-server 'sudo certbot certificates'
ssh xmu-server 'systemctl status certbot.timer --no-pager'
ssh xmu-server 'sudo certbot renew --dry-run'
```

自动续期模拟已成功。保持 80 端口和 ACME 路径可访问，才能继续使用此验证方式。日常网页发布只替换静态文件，不会修改 Nginx 或证书。

域名注册、DNS 与 HTTPS 不代表已完成 ICP 备案。上海服务器正式通过域名提供网站前，需要完成适用的备案与接入手续；当前尚未确认备案状态。参见[腾讯云说明](https://cloud.tencent.com/document/product/243/19630/)。

首次安装由管理员安装 Ubuntu 仓库的 Nginx，将 `activate.py` 安装到上述程序路径，把 `nginx.conf` 放入 Nginx 的 `sites-available` 并启用。配置变更后必须先运行 `sudo nginx -t` 再 reload；日常发布仅切换静态文件版本，无需重启 Nginx。
