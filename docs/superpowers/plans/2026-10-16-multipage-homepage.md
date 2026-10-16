# Multipage Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 首页仅保留个人介绍与完整教育经历，各兴趣模块通过独立页面访问。

**Architecture:** 保留静态 GitHub Pages 架构，共享 CSS/JS，各 HTML 可直接访问与刷新。按页面中的实际元素初始化交互，首页不请求文章或照片索引。

**Tech Stack:** HTML、CSS、原生 JavaScript、Python HTTP server。

### 1. 页面拆分

- [x] `index.html`：保留森林首屏与个人介绍，补充教育经历：厦门大学（2024—至今）、哈尔滨德强高中、嫩江市第一中学。后两者不编造年份。
- [x] `photos.html`：迁移图片分类、作者署名和灯箱；`writing.html`：文章索引与空状态；`reading.html`：迁移原有五条哲学原文；`projects.html`：项目空状态及公开仓库入口。
- [x] 所有页共享指向真实 HTML 的导航、当前页标记、返回首页入口和主题偏好。

### 2. 共享资源

- [x] `assets/site.js`：语录按钮、首屏景深、图库、文章索引均在对应元素存在时初始化。
- [x] `assets/site.css`：子页面标题、教育列表与手机排版，延续冷峻文案及深色风格。
- [x] `README.md`：补充页面地图，保留原有内容 JSON 格式。

### 3. 验证与发布

- [x] HTML 引用/锚点、JS 语法、Git 差异检查通过。
- [x] 浏览器从首页逐一进入模块，验证返回、直接刷新、语录、图库灯箱和空状态；手机菜单及无横向溢出。
- [x] 独立代码审查并修复实际问题，保存截图与本地提交。
- [ ] 延续用户的 GitHub Pages 发布请求：先解决已发现的 Git 认证失败，再发布并检查线上构建；认证未解决时明确说明状态。
