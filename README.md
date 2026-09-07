# 陈炳奇 · Forest 个人网站

这是一个无需构建的 GitHub Pages 静态站点。把内容推送到 `main` 分支后，GitHub Pages 会自动更新。

页面右上角的“主题”按钮可在黑白浅色与深色界面间切换；网站会记住访客的选择。首页语录按钮会轮换显示哲学名著的原文及出处。

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

推荐将单张图片压缩到 2 MB 以内。写作和摄影记录均按最新内容放在数组最前面。

## 开启发布

GitHub 仓库中依次打开 **Settings → Pages**，在 **Build and deployment** 中选择 **Deploy from a branch**，设置为 `main` 分支和 `/ (root)` 文件夹。保存后访问 `https://chenforest-love.github.io/`。
