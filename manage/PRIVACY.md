# 相册密码

功能已提供；现有四个相册依照作者要求保持公开，密码均未设置。

## 使用

在仓库内运行 `./manage/start.ps1`（会识别并重启旧版管理进程），打开本机管理页 `http://127.0.0.1:4180/photos.html`。每册下方有「设置相册密码」，也可进入册页后设置：

1. 输入并确认至少 14 位的相册密码。
2. 点击「保存并发布 GitHub」。本机将照片与缩略图加密，生成模糊封面，提交到 GitHub；不触发腾讯云同步。
3. GitHub Pages 更新后，访客只能看到模糊封面与锁标识，进入后输入密码查看照片。

密码只在本机处理和浏览器解密时使用，不写入仓库、日志或命令参数。请自行保管；没有密码找回入口。

已锁定的册可以通过「管理相册密码」验证旧密码后修改密码或取消保护。取消保护会将照片重新公开提交 GitHub。暂不支持直接替换锁定册的封面：需先取消保护、选择封面，再重新设置密码。

推送失败时，加密提交保留在本地，点击「重试推送 GitHub」即可重试，不必重新设置密码。修改过程中保持 `main` 和干净工作区；发布器只提交该册涉及的文件，拒绝混入无关开发提交。提交失败会恢复自己的未提交变更。

## 保护范围

这是对**当前版本照片文件**的加密，不只是隐藏网页内容。锁定时，当前目录的清晰图、缩略图、公开索引与无 JavaScript 回退里的明文引用一起移除；公开页面只保留册名、数量、实际模糊后的低分辨率封面和密文。

过去已经公开的照片可能仍存在于 Git 历史、旧服务器、缓存或下载副本。此功能不会清理这些副本，也不会重写 Git 历史；改密码只影响新版本，旧密码仍然能解开 Git 历史中保留的旧密文。若照片尚未公开，应在首次推送前加密，而不是先公开再设密码。当前工作约定仍是仅更新 GitHub，腾讯云后续由作者明确要求再同步。

模糊封面仍会透露大致颜色和轮廓。解锁后的访客可以保存所见图片；此功能不限制截图或下载。

## 技术和维护

- 本机打包：Python、Pillow 和 cryptography；当前 Codex 捆绑 Python 已具备，无需在服务器安装任何依赖。
- 每册随机 16 字节 salt、12 字节 IV，PBKDF2-SHA256 600000 次派生 AES-256-GCM 密钥，认证关联数据绑定册 ID。
- 密文：`content/photos/private/<册ID>.enc.json`；模糊封面：`content/photos/images/<册ID>-locked.webp`。
- 浏览器使用 Web Crypto 解密，照片使用内存 blob URL。刷新或重新锁定后需再次输入密码；不把密码或解锁状态存入 localStorage/sessionStorage。
- GitHub Pages HTTPS、本机 localhost/127.0.0.1 预览支持解密；普通公网 HTTP 不支持 Web Crypto。
- 单册明文图片总量上限 24 MiB，适合个人图册；更大图册请先压缩或拆分。
- 仓库默认封面和服务器封面覆盖接口都不能用清晰图替换锁定册的模糊封面。

验证命令：`python -m unittest discover -s manage -p "test_*.py"`。测试只操作隔离目录和临时 Git 仓库，不推送、不给真实相册加锁、不连接腾讯云。

实现依据：[Web Crypto AES-GCM](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/encrypt)、[密钥派生](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/deriveKey)。
