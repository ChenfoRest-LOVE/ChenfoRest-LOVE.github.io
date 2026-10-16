# 陈炳奇 · Forest 个人网站

深色沉浸式个人网站，围绕影像、哲学阅读与随笔展开。HTML、CSS 和原生 JavaScript，无需安装依赖或构建。首页仅展示个人介绍与教育经历，各模块通过独立页面访问，支持 GitHub Pages。

## 本地预览

在本目录运行：

```powershell
python -m http.server 4173 --bind 127.0.0.1
```

打开 <http://127.0.0.1:4173/>，修改文件后刷新。不要直接双击 HTML：本地文件限制会阻止 JSON 加载。

默认深色，可切换浅色并记住选择。支持手机导航、照片分类与键盘灯箱；减少动态系统偏好会关闭动画。

## 页面结构

首页仅保留个人介绍与教育经历。各模块为独立静态页面，点击导航进入，可直接打开或刷新，不依赖前端路由服务器：

| 页面 | 内容 |
| --- | --- |
| `index.html` | 个人介绍、厦门大学、哈尔滨德强高中、嫩江市第一中学 |
| `photos.html` | 影像档案、分类与灯箱 |
| `writing.html` | 随笔与阅读记录索引 |
| `reading.html` | 哲学原文摘录与出处 |
| `projects.html` | 项目索引与公开代码仓库入口 |

高中与初中的就读年份尚未提供，页面只展示学校与阶段。各页面共用 `assets/site.css`、`assets/theme.css`、`assets/site.js`；首页不会加载文章或照片索引。

## 预览影像来源

这些是版式示例，**不是陈炳奇的摄影作品**。图片已保存在本地，完整来源记录在 `assets/images/credits.json`。

| 文件 | 摄影师 | 原始页面 |
| --- | --- | --- |
| forest-hero.jpg | Marvin Zettl | [雾中森林](https://unsplash.com/photos/a-dark-forest-filled-with-lots-of-trees-reoc0yCf67c) |
| forest-detail.jpg | Fethi Benattallah | [高树与雾](https://unsplash.com/photos/tall-trees-in-a-dark-misty-forest-DL50VDF9yy4) |
| coast.jpg | Dylan Crawford | [海岸与礁石](https://unsplash.com/photos/misty-ocean-waves-crash-over-dark-rocks-UeqVDsvBkUc) |

图片遵循 [Unsplash License](https://unsplash.com/license)。更换首屏图片 `assets/images/forest-hero.jpg` 时同步更新署名。照片索引为空时展示示例；加入有效个人照片后自动替换示例画廊。

日常更新可将开发分支推送并创建 Pull Request，审阅后合并到 `main`。仓库启用 Pages 分支发布后，`main` 的更新会触发网站部署。不要提交服务器密码、令牌或密钥。

页面右上角的主题按钮可在浅色与深色界面间切换；网站会记住访客的选择。语录按钮会轮换显示哲学名著的原文及出处。

## 新增写作

1. 在 `content/writing/` 新建文章 HTML 文件，例如 `first-note.html`。
2. 在 `content/writing/index.json` 中加入一条记录：

```json
[
  {
    "title": "文章标题",
    "date": "2026.09.07",
    "summary": "一两句简介。",
    "file": "first-note.html"
  }
]
```

## 新增摄影

1. 将图片上传到 `content/photos/`，例如 `xiamen-sunset.jpg`。
2. 在 `content/photos/index.json` 中加入一条记录：

```json
[
  {
    "file": "xiamen-sunset.jpg",
    "alt": "厦门的傍晚",
    "caption": "厦门 · 2026"
  }
]
```

摄影可增加可选 `category` 字段进行分类；原有三个字段保持兼容。推荐将单张图片压缩到 2 MB 以内。写作和摄影记录均按最新内容放在数组最前面。以上仅为数据格式示例，不代表已有作品。文件路径只使用各自内容目录内的相对路径。文章 HTML 需自带阅读样式。

## 开启发布

GitHub 仓库中依次打开 **Settings → Pages**，在 **Build and deployment** 中选择 **Deploy from a branch**，设置为 `main` 分支和 `/ (root)` 文件夹。保存后访问 `https://chenforest-love.github.io/`。

## 腾讯云部署

国内服务器使用 Nginx 提供相同的静态页面，GitHub `main` 继续作为代码来源。将修改推送到 `main` 后，在已配置专用 SSH 连接的本机运行 `./deploy/publish.ps1` 即可同步；`./deploy/publish.ps1 -Rollback` 可切回上一版。

部署只上传网页、图片和内容索引，每个版本按 Git SHA 独立保存，切换不需要重启服务。完整说明见 [deploy/README.md](deploy/README.md)。目前以 IP 进行验收；正式域名访问需要完成适用的备案、域名解析与 HTTPS 配置。
