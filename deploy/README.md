# 腾讯云静态部署

GitHub `main` 为唯一代码来源。发布脚本在本机获取 `origin/main`，用 `git archive` 只打包五个 HTML、`assets/` 和 `content/`，通过既有 SSH 别名上传。未提交改动、Git 凭据、文档与部署脚本不会进入网站根目录。服务器无需保存 GitHub 写入凭据。

## 更新网站

先将代码推送到 GitHub `main`，再在本机 PowerShell 运行：

```powershell
./deploy/publish.ps1
```

此命令是手动发布，没有定时轮询。需要本机已配置 `ssh xmu-server` 和专用 SSH 密钥；私钥不属于仓库。

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

当前 Nginx 配置用于 IP 验收。上海服务器正式通过域名提供网站前，需要完成适用的备案与接入手续，随后绑定域名、配置解析和 HTTPS。IP 测试与正式对外服务的区别见[腾讯云说明](https://cloud.tencent.com/document/product/243/19630/)。未提供域名时不填写虚构域名或备案号。

首次安装由管理员安装 Ubuntu 仓库的 Nginx，将 `activate.py` 安装到上述程序路径，把 `nginx.conf` 放入 Nginx 的 `sites-available` 并启用。配置变更后必须先运行 `sudo nginx -t` 再 reload；日常发布仅切换静态文件版本，无需重启 Nginx。
