// Real local API, temporary database, isolated browser accounts. No external site visits.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || `${process.env.USERPROFILE}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`);
const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const python = process.env.TEST_PYTHON || `${process.env.USERPROFILE}/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`;
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'forest-comments-test-'));
const port = 4194, base = `http://127.0.0.1:${port}`;
const child = spawn(python, ['-u', path.join(__dirname, 'server.py'), '--port', String(port), '--root', root, '--data', path.join(temp, 'test.sqlite')], { windowsHide: true, stdio: 'ignore' });
const password = 'Browser-test-only-password-2026!';
let browser, checks = [];
async function check(name, action) { await action(); checks.push(name); }
async function register(page, username) {
  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByRole('button', { name: '创建账号', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '创建账号' });
  await dialog.getByLabel('用户名', { exact: true }).fill(username);
  await dialog.getByLabel('密码', { exact: true }).fill(password);
  await dialog.getByLabel('确认密码', { exact: true }).fill(password);
  await dialog.getByRole('button', { name: '注册并登录' }).click();
  await dialog.waitFor({ state: 'hidden' });
}
(async () => {
  for (let n = 0; n < 100; n++) {
    if (child.exitCode !== null) throw new Error('Fixture server exited');
    try { if ((await fetch(`${base}/api/community/health`)).ok) break; } catch {}
    await new Promise(r => setTimeout(r, 100));
    if (n === 99) throw new Error('Fixture server did not start');
  }
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}/content/writing/chire.html`);
  await check('article has a comment section', async () => assert.equal(await page.locator('#comments').count(), 1));
  await check('public empty state and login prompt', async () => {
    await page.getByText('暂无评论。', { exact: true }).waitFor();
    assert.equal(await page.locator('[data-comment-form]').isVisible(), false);
  });
  let releaseInitialList;
  const heldList = new Promise(resolve => { releaseInitialList = resolve; });
  let initialListHeld = false;
  await page.route('**/api/community/comments?article=chire', async route => {
    if (initialListHeld) return route.continue();
    initialListHeld = true;
    const response = await route.fetch();
    const body = await response.text();
    await heldList;
    await route.fulfill({ response, body });
  });
  await check('registration and automatic login', async () => {
    await register(page, 'reader_one');
    await page.getByText('reader_one', { exact: true }).waitFor();
    assert(await page.locator('[data-comment-form]').isVisible());
  });
  await check('counter matches server whitespace rules', async () => {
    await page.getByLabel('评论内容').fill('\ufeff' + '字'.repeat(100));
    assert.equal(await page.locator('[data-comment-count]').textContent(), '101 / 100');
    await page.getByLabel('评论内容').fill('\u0085' + '字'.repeat(100) + '\u0085');
    assert.equal(await page.locator('[data-comment-count]').textContent(), '100 / 100');
  });
  await check('100 Unicode codepoints accepted; 101 rejected in UI', async () => {
    const textarea = page.getByLabel('评论内容');
    await textarea.fill('🌒'.repeat(101));
    assert.equal(await page.locator('[data-comment-count]').textContent(), '101 / 100');
    assert(await page.getByRole('button', { name: '发表评论', exact: true }).isDisabled());
    await textarea.fill('🌒'.repeat(100));
    assert.equal(await page.locator('[data-comment-count]').textContent(), '100 / 100');
    await page.getByRole('button', { name: '发表评论', exact: true }).click();
    await page.locator('[data-comment-list] article').waitFor();
    assert.equal(await textarea.inputValue(), '');
  });
  await check('late comment list cannot erase a successful submission', async () => {
    releaseInitialList();
    await page.waitForResponse(response => response.request().method() === 'GET' && response.url().endsWith('/comments?article=chire'));
    await page.waitForTimeout(150);
    assert.equal(await page.locator('[data-comment-list] article').count(), 1);
    await page.unroute('**/api/community/comments?article=chire');
  });
  await check('refresh persists account and comment', async () => {
    await page.reload();
    await page.locator('[data-comment-list] article').waitFor();
    assert(await page.locator('[data-comment-form]').isVisible());
    assert.equal(await page.locator('[data-comment-list] article').count(), 1);
  });
  await check('separate articles and shared session', async () => {
    await page.goto(`${base}/content/writing/yuemeng.html`);
    await page.getByText('暂无评论。', { exact: true }).waitFor();
    assert(await page.locator('[data-comment-form]').isVisible());
    await page.goto(`${base}/content/writing/chire.html`);
    await page.locator('[data-comment-list] article').waitFor();
  });
  await check('rate limit preserves draft', async () => {
    await page.getByLabel('评论内容').fill('保留的草稿');
    await page.getByRole('button', { name: '发表评论', exact: true }).click();
    await page.locator('[data-comment-status]').filter({ hasText: '操作频繁' }).waitFor();
    assert.equal(await page.getByLabel('评论内容').inputValue(), '保留的草稿');
  });
  const secondContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const second = await secondContext.newPage();
  await second.goto(`${base}/content/writing/chire.html`);
  await check('another reader can read but cannot delete', async () => {
    await second.locator('[data-comment-list] article').waitFor();
    await register(second, 'reader_two');
    assert.equal(await second.locator('[data-comment-list] [data-delete]').count(), 0);
  });
  await check('untrusted text is displayed literally', async () => {
    await second.getByLabel('评论内容').fill('<img src=x onerror=alert(1)>');
    // The shared-IP burst limit is per hour, not per user per 30 seconds.
    await second.getByRole('button', { name: '发表评论', exact: true }).click();
    await second.locator('[data-comment-list] p').filter({ hasText: '<img src=x onerror=alert(1)>' }).waitFor();
    assert.equal(await second.locator('[data-comment-list] img').count(), 0);
  });
  await check('delete own comment only', async () => {
    await second.locator('[data-delete]').click();
    await second.getByRole('button', { name: '确认删除' }).click();
    await second.locator('[data-delete]').waitFor({ state: 'detached' });
    assert.equal(await second.locator('[data-comment-list] article').count(), 1);
  });
  await check('mobile and light theme remain within viewport', async () => {
    await second.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
    await second.locator('#comments').scrollIntoViewIfNeeded();
    assert(await second.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const shot = process.env.COMMENTS_SCREENSHOT || path.join(temp, 'comments-mobile.png');
    await second.screenshot({ path: shot });
    if (process.env.COMMENTS_SCREENSHOT) console.log(`Screenshot: ${shot}`);
    await second.setViewportSize({ width: 320, height: 720 });
    assert(await second.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  });
  await check('logout, login and keyboard dismissal', async () => {
    await page.getByRole('button', { name: '退出', exact: true }).click();
    await page.getByRole('button', { name: '登录', exact: true }).waitFor();
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').isVisible(), false);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '登录' });
    await dialog.getByLabel('用户名', { exact: true }).fill('READER_ONE');
    await dialog.getByLabel('密码', { exact: true }).fill(password);
    await dialog.getByRole('button', { name: '登录', exact: true }).click();
    await dialog.waitFor({ state: 'hidden' });
    assert(await page.locator('[data-comment-form]').isVisible());
  });
  await check('session expiry preserves a comment draft and requests login', async () => {
    await context.clearCookies();
    await page.getByLabel('评论内容').fill('会话失效后的草稿');
    await page.getByRole('button', { name: '发表评论', exact: true }).click();
    await page.getByRole('button', { name: '登录', exact: true }).waitFor();
    assert.equal(await page.getByLabel('评论内容').inputValue(), '会话失效后的草稿');
  });
  await check('posting during initial load retains existing comments and pagination', async () => {
    execFileSync(python, ['-c', `import sqlite3,sys,time
db=sqlite3.connect(sys.argv[1])
for n in range(25): db.execute('INSERT INTO comments(article,user_id,text,created) VALUES (?,?,?,?)',('yuemeng',1,'Earlier comment '+str(n),time.time()))
db.commit()
db.close()`, path.join(temp, 'test.sqlite')], { windowsHide: true });
    const raceContext = await browser.newContext();
    const race = await raceContext.newPage();
    await race.goto(`${base}/content/writing/yuemeng.html`);
    await race.locator('[data-comment-list] article').first().waitFor();
    const authenticatedList = race.waitForResponse(r => r.request().method() === 'GET' && r.url().endsWith('/comments?article=yuemeng'));
    await register(race, 'reader_race');
    await authenticatedList;
    await race.waitForTimeout(100);
    let release, held = false, listStarted;
    const gate = new Promise(resolve => { release = resolve; });
    const started = new Promise(resolve => { listStarted = resolve; });
    await race.route('**/api/community/comments?article=yuemeng', async route => {
      if (held) return route.continue();
      held = true; const response = await route.fetch(); const body = await response.text(); listStarted();
      await gate; await route.fulfill({ response, body });
    });
    await race.reload(); await started;
    await race.locator('[data-comment-form]').waitFor({ state: 'visible' });
    await race.getByLabel('评论内容').fill('New comment during loading');
    await race.getByRole('button', { name: '发表评论', exact: true }).click();
    await race.locator('[data-comment-list] p').filter({ hasText: 'New comment during loading' }).waitFor();
    const releasedResponse = race.waitForResponse(r => r.request().method() === 'GET' && r.url().endsWith('/comments?article=yuemeng'));
    release(); await releasedResponse;
    await race.waitForTimeout(200);
    assert.equal(await race.locator('[data-comment-list] article').count(), 20);
    assert(await race.getByRole('button', { name: '更早的评论' }).isVisible());
    await race.getByRole('button', { name: '更早的评论' }).click();
    await race.getByRole('button', { name: '更早的评论' }).waitFor({ state: 'hidden' });
    assert.equal(await race.locator('[data-comment-list] article').count(), 26);
    assert.equal(new Set(await race.locator('[data-comment-list] article').evaluateAll(nodes => nodes.map(n => n.dataset.id))).size, 26);
    await raceContext.close();
  });
  await check('static deployment is visibly disabled without API requests', async () => {
    const staticContext = await browser.newContext();
    const staticPage = await staticContext.newPage();
    const apiCalls = [];
    staticPage.on('request', r => { if (r.url().includes('/api/community/')) apiCalls.push(r.url()); });
    await staticPage.route('**/assets/comments-config.js*', route => route.fulfill({ contentType: 'text/javascript', body: 'window.FOREST_COMMENTS={enabled:false};' }));
    await staticPage.goto(`${base}/content/writing/chire.html`);
    await staticPage.getByText('评论暂未开放。', { exact: true }).waitFor();
    assert.equal(apiCalls.length, 0);
    assert.equal(await staticPage.getByRole('button', { name: '登录', exact: true }).count(), 0);
    await staticContext.close();
  });
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
})().catch(error => { console.error(error.stack); process.exitCode = 1; }).finally(async () => {
  child.kill();
  if (browser) await Promise.race([browser.close(), new Promise(r => setTimeout(r, 4000))]);
  // Temporary fixture data contains test accounts only; OS temp cleanup handles leftovers on Windows.
  process.exit(process.exitCode || 0);
});
