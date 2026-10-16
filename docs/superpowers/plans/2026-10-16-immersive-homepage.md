# Immersive Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 完成 Forest 深色沉浸式个人主页并提供本地预览。

**Architecture:** 保持无需构建的静态站点。HTML 定义内容和语义，CSS 管理响应式视觉，JavaScript 管理主题、内容索引与影像浏览；不引入服务端。

**Tech Stack:** HTML5, CSS, vanilla JavaScript, Python HTTP server, browser interaction checks.

---

### Task 1: 页面和交互

**Files:** `index.html`, `assets/site.css`, `assets/theme.css`, `assets/site.js`, `assets/favicon.svg`。

- [x] 重做通栏森林海报、影像、哲学语录、随笔和关于区，默认深色；所有个人事实取自现有仓库。
- [x] 保留 writing `{title,date,summary,file}` 和 photos `{file,alt,caption}` 数据接口，DOM 使用 textContent，拒绝跨目录资源路径。
- [x] 实现分类、灯箱、主题记忆、移动导航、减少动态支持；空内容和加载失败均有可读状态。
- [x] 运行 `node --check assets/site.js` 和 `git diff --check`，预期退出码 0。

### Task 2: 素材与使用文档

**Files:** `assets/images/{forest-hero,forest-detail,coast}.jpg`, `assets/images/credits.json`, `README.md`。

- [x] 下载并压缩已核实来源的图片，保存作者、原始页面与许可证链接，标记仅为示例影像。
- [x] 文档写明本地命令 `python -m http.server 4173 --bind 127.0.0.1`、数据更新方法及未来 GitHub 流程。

### Task 3: 实际浏览器验收

- [x] 在现有 `http://127.0.0.1:4173/` 标签页刷新，检查首屏图片和所有区块。
- [x] 桌面检查图片分类、灯箱上一张/下一张、Escape 关闭、语录切换、主题刷新记忆。
- [x] 手机宽度检查菜单开合和锚点跳转、内容无横向溢出；截图留档。
- [x] 检查浏览器错误、资源完整性和 JSON 内容接口兼容；独立进行需求审查与代码质量审查，修复问题。
- [x] 完成本地提交并保留分支 `codex/immersive-homepage`；不推送或部署。
