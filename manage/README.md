# 本机默认封面维护（旧入口）

日常封面管理已改为 `https://denss.asia/admin/`，详见 `remote_admin/README.md`。此旧入口只维护 Git 仓库中的静态默认封面；在线后台已保存的选择优先，不会被本机默认值覆盖。域名 API 不可达或禁用 JavaScript 时展示静态默认封面。

此服务仅在这台电脑上运行，使用本机现有 GitHub 登录和 `ssh xmu-server`，不需要额外账号。

## 使用

在网站仓库的 PowerShell 中运行：

```powershell
./manage/start.ps1
```

打开 `http://127.0.0.1:4180/photos.html`，进入相册，在照片下点击“设为封面”。按钮将更新 `content/photos/albums.json` 和静态图册目录，提交到 GitHub `main`，再同步腾讯云；GitHub Pages 通常稍后完成更新。当前封面再次点击可重新同步。网络或发布失败时按页面提示重试。

管理服务只监听本机回环地址，其他访客无法访问。管理会话和防跨站请求令牌只保存在进程与浏览器中，不写入仓库、配置或日志。不要把此服务映射到公网。

停止服务：

```powershell
./manage/start.ps1 -Stop
```

## 发布约束

- 必须位于 `main` 且没有未提交修改；管理过程中不要同时编辑封面配置与图册目录。
- 自动同步远程版本，拒绝混入本地尚未发布的其他开发提交。
- 只提交两个封面相关文件；提交前失败会恢复自身尚未提交的修改。完成的封面提交会保留供推送重试。
- 不强制推送，不保存 GitHub token、服务器密码或私钥。已有 GitHub 凭据失效时，需要在本机重新登录。
- 腾讯云部署传入确切提交 SHA；发现远程版本改变则停止本次部署，刷新后重试。
- 推送成功但服务器同步失败时，会明确提示，不会宣称全站同步成功。

## 验证

Python 标准库即可运行测试，无需安装依赖：

```powershell
python -m unittest discover -s manage -p test_manager.py -v
```

测试覆盖照片归属、静态封面生成、Host/Origin/会话/CSRF 校验、文件读取范围、并发保护、提交失败恢复、真实临时 Git 仓库的重试，以及 PowerShell 部署版本检查。测试不推送 GitHub，也不操作真实服务器。
