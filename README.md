# 陈炳奇 · Forest 个人网站

深色沉浸式个人网站，围绕影像、哲学阅读与随笔展开。HTML、CSS 和原生 JavaScript，无需安装依赖或构建。首页仅展示个人介绍与教育经历，各模块通过独立页面访问，支持 GitHub Pages。

## 本地预览

在本目录运行：

```powershell
python -m http.server 4173 --bind 127.0.0.1
```

打开 <http://127.0.0.1:4173/>，修改文件后刷新。不要直接双击 HTML：本地文件限制会阻止 JSON 加载。

默认深色，可切换浅色并记住选择。支持手机导航、照片分类与键盘灯箱；减少动态系统偏好会关闭动画。

### 含账号与评论的预览

文章末尾均有评论区。运行 `./community/start.ps1`，打开 `http://127.0.0.1:4192/writing.html`，可在文章下注册独立访客账号、登录并发表不超过 100 字的评论。账号与评论数据保存在仓库外，刷新和重启后保留；支持删除自己的评论。

当前按备案期间的约定先在本地验收，GitHub Pages 显示“评论暂未开放”。普通静态预览与封面管理入口也不会启动评论后端。使用方式、数据位置与未来上线步骤见 [评论说明](community/README.md)，本次不部署腾讯云。

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

下表为首页氛围图及保留的版式示例素材，**不是陈炳奇的摄影作品**，不属于现有四个个人图册。图片已保存在本地，完整来源记录在 `assets/images/credits.json`。

| 文件 | 摄影师 | 原始页面 |
| --- | --- | --- |
| forest-hero.jpg | Marvin Zettl | [雾中森林](https://unsplash.com/photos/a-dark-forest-filled-with-lots-of-trees-reoc0yCf67c) |
| forest-detail.jpg | Fethi Benattallah | [高树与雾](https://unsplash.com/photos/tall-trees-in-a-dark-misty-forest-DL50VDF9yy4) |
| coast.jpg | Dylan Crawford | [海岸与礁石](https://unsplash.com/photos/misty-ocean-waves-crash-over-dark-rocks-UeqVDsvBkUc) |

图片遵循 [Unsplash License](https://unsplash.com/license)。更换首屏图片 `assets/images/forest-hero.jpg` 时同步更新署名。影像模块已使用用户提供的五张照片，分为哈尔滨、嫩江、良友佳侣和个人四册；加载失败时显示提示，不会混入示例图片。

日常更新可将开发分支推送并创建 Pull Request，审阅后合并到 `main`。仓库启用 Pages 分支发布后，`main` 的更新会触发网站部署。不要提交服务器密码、令牌或密钥。

页面右上角的主题按钮可在浅色与深色界面间切换；网站会记住访客的选择。语录按钮会轮换显示哲学名著的原文及出处。

## 新增写作

1. 在 `content/writing/` 新建文章 HTML 文件，例如 `first-note.html`。
2. 在 `content/writing/index.json` 中加入一条记录：

```json
[
  {
    "title": "文章标题",
    "date": "2026-09-07",
    "file": "first-note.html"
  }
]
```

文字目录只显示标题与写作日期，整行点击后进入文章。日期使用 `YYYY-MM-DD`，按最新内容在前排列。正文页可参考 `content/writing/chire.html` 与 `yuemeng.html`，共用 `assets/writing.css`；保留原文段落，按需调整排版。现有两篇文章的写作日期由作者确认，未从文件接收时间推断。

## 新增摄影

1. 将图片上传到 `content/photos/images/`，生成清晰图和较小的预览图。
2. 在 `content/photos/index.json` 中加入一条记录：

```json
[
  {
    "file": "images/xiamen-sunset-full.webp",
    "thumbnail": "images/xiamen-sunset-thumb.webp",
    "width": 1920,
    "height": 1280,
    "alt": "厦门的傍晚",
    "caption": "傍晚",
    "category": "personal",
    "categoryLabel": "个人"
  }
]
```

`photos.html` 展示四个图册封面，点击后进入 `content/photos/harbin.html`、`nenjiang.html`、`companions.html` 或 `personal.html`。图册页根据 `data-album` 筛选索引，预览图用于页面加载，点击后加载清晰图；单册内支持键盘翻页和原比例预览。添加照片时同步更新封面页和对应册页的数量与无 JavaScript 备用内容。新增图册可沿用现有册页结构。

封面配置保存在 `content/photos/albums.json`。更换全站封面可运行 `./manage/start.ps1`，从仅本机可访问的管理页进入相册并点击“设为封面”；会通过现有 GitHub 与 SSH 发布流程同步到网站。公开页面没有管理按钮。详见 [封面管理说明](manage/README.md)。

`thumbnail`、`width`、`height` 为建议字段，原有 `file`、`alt`、`caption` 三字段保持兼容；尺寸应为清晰图的真实像素。推荐清晰图长边不超过 2560 像素且单张小于 2 MB，不放大低分辨率照片。发布图已统一色彩并去除原始元数据。当前五张图片没有可用拍摄日期或 GPS，地点与图册由用户确认，未编造时间或人物关系。示例 JSON 仅说明格式。文件路径只使用对应内容目录内的相对路径。文章 HTML 需自带阅读样式。

## 开启发布

GitHub 仓库中依次打开 **Settings → Pages**，在 **Build and deployment** 中选择 **Deploy from a branch**，设置为 `main` 分支和 `/ (root)` 文件夹。保存后访问 `https://chenforest-love.github.io/`。

## 腾讯云部署

国内服务器使用 Nginx 提供相同的静态页面，GitHub `main` 继续作为代码来源。将修改推送到 `main` 后，在已配置专用 SSH 连接的本机运行 `./deploy/publish.ps1` 即可同步；`./deploy/publish.ps1 -Rollback` 可切回上一版。

部署只上传网页、图片和内容索引，每个版本按 Git SHA 独立保存，切换不需要重启服务。国内域名为 `denss.asia`，支持 `www.denss.asia`，已配置 HTTP 跳转 HTTPS 和证书自动续期。2026-10-16 观察到腾讯云未备案拦截，当前国内域名不能正常访问，需完成备案后复查；文章和网页代码已部署在服务器上。现可访问 [GitHub Pages](https://chenforest-love.github.io/)。配置、续期与验收说明见 [deploy/README.md](deploy/README.md)。
