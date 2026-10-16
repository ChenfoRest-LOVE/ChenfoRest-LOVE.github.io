# 陈炳奇 · Forest 个人网站

深色沉浸式主页，围绕影像、哲学阅读与随笔展开。HTML、CSS 和原生 JavaScript，无需安装依赖或构建。当前本地分支 `codex/immersive-homepage`，本次只本地预览，未推送或部署。

## 本地预览

在本目录运行：

```powershell
python -m http.server 4173 --bind 127.0.0.1
```

打开 <http://127.0.0.1:4173/>，修改文件后刷新。不要直接双击 HTML：本地文件限制会阻止 JSON 加载。

默认深色，可切换浅色并记住选择。支持手机导航、照片分类与键盘灯箱；减少动态系统偏好会关闭动画。

## 预览影像来源

这些是版式示例，**不是陈炳奇的摄影作品**。图片已保存在本地，完整来源记录在 `assets/images/credits.json`。

| 文件 | 摄影师 | 原始页面 |
| --- | --- | --- |
| forest-hero.jpg | Marvin Zettl | [雾中森林](https://unsplash.com/photos/a-dark-forest-filled-with-lots-of-trees-reoc0yCf67c) |
| forest-detail.jpg | Fethi Benattallah | [高树与雾](https://unsplash.com/photos/tall-trees-in-a-dark-misty-forest-DL50VDF9yy4) |
| coast.jpg | Dylan Crawford | [海岸与礁石](https://unsplash.com/photos/misty-ocean-waves-crash-over-dark-rocks-UeqVDsvBkUc) |

图片遵循 [Unsplash License](https://unsplash.com/license)。更换首屏图片 `assets/images/forest-hero.jpg` 时同步更新署名。照片索引为空时展示示例；加入有效个人照片后自动替换示例画廊。

这是一个无需构建的 GitHub Pages 静态站点。后续确认设计后，可将开发分支推送并创建 Pull Request，审阅后合并到 `main`；是否触发公开发布由仓库 Pages 设置决定。不要提交服务器密码、令牌或密钥。

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
