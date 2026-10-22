/* Reader UI. User content is inserted as text, never interpreted as HTML. */
(() => {
  'use strict';
  const root = document.querySelector('[data-comments-article]');
  if (!root || window.FOREST_COMMENTS?.enabled !== true) return;
  const article = root.dataset.commentsArticle;
  const api = '/api/community/';
  let user = null, csrf = null, next = null, pending = false, authPending = false, mode = 'login', selected = null;
  let revision = 0, loadId = 0, initializationId = 0;
  let feedbackId = 0;
  root.innerHTML = `
    <div class="comments-heading"><h2 id="comments-title">评论</h2><div class="comments-account" data-account></div></div>
    <p class="comments-note" data-guest hidden>登录后发表评论。</p>
    <form class="comment-compose" data-comment-form hidden>
      <label for="comment-text">评论内容</label>
      <textarea id="comment-text" name="text" rows="3" aria-describedby="comment-count comment-rule" required></textarea>
      <div class="comment-compose-footer"><output id="comment-count" data-comment-count>0 / 100</output><button class="comment-submit" type="submit">发表评论</button></div>
      <p class="comments-note" id="comment-rule">最多 100 字，含标点。每次评论间隔至少 30 秒。</p>
    </form>
    <p class="comments-status" data-comment-status role="status" aria-live="polite">正在加载评论…</p>
    <button class="comment-link" type="button" data-retry hidden>重新加载</button>
    <div class="comment-list" data-comment-list aria-label="评论列表"></div>
    <p class="comments-empty" data-empty hidden>暂无评论。</p>
    <button class="comment-link comments-more" type="button" data-more hidden>更早的评论</button>
    <dialog class="reader-dialog" data-auth aria-labelledby="reader-title">
      <div class="reader-dialog-heading"><h2 id="reader-title">登录</h2><button class="comment-link" type="button" data-close aria-label="关闭登录窗口">关闭</button></div>
      <form data-auth-form>
        <label>用户名<input name="username" autocomplete="username" autocapitalize="none" spellcheck="false" minlength="3" maxlength="32" pattern="[A-Za-z0-9_.\\-]{3,32}" required /></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" maxlength="256" required /></label>
        <label data-confirm hidden>确认密码<input name="confirm" type="password" autocomplete="new-password" maxlength="256" /></label>
        <small data-register-note hidden>用户名 3–32 位，可用字母、数字及 _ . -；密码 12–128 个字符。请妥善保存密码，暂不提供在线找回。</small>
        <p class="reader-status" data-auth-status role="status" aria-live="polite"></p>
        <div class="reader-dialog-actions"><button class="comment-link" type="button" data-mode>创建账号</button><button class="comment-submit" type="submit" data-auth-submit>登录</button></div>
      </form>
    </dialog>
    <dialog class="reader-dialog" data-delete-dialog aria-labelledby="delete-title">
      <div class="reader-dialog-heading"><h2 id="delete-title">删除评论</h2></div>
      <p>删除后无法恢复。</p><p class="reader-status" data-delete-status role="status"></p>
      <div class="reader-dialog-actions"><button class="comment-link" type="button" data-cancel-delete>取消</button><button class="comment-submit" type="button" data-confirm-delete>确认删除</button></div>
    </dialog>`;
  const $ = selector => root.querySelector(selector);
  const form = $('[data-comment-form]'), textarea = $('#comment-text'), status = $('[data-comment-status]');
  const list = $('[data-comment-list]'), auth = $('[data-auth]'), authForm = $('[data-auth-form]');
  const deleteDialog = $('[data-delete-dialog]');
  const button = (name, action) => {
    const node = document.createElement('button');
    node.type = 'button'; node.className = 'comment-link'; node.textContent = name;
    node.addEventListener('click', action);
    return node;
  };
  function message(text = '', error = false) { feedbackId++; status.textContent = text; status.dataset.error = String(error); }
  function count() {
    // Unicode White_Space plus U+001C–001F exactly matches Python str.strip().
    const text = textarea.value.normalize('NFC').replace(/^[\p{White_Space}\u001c-\u001f]+|[\p{White_Space}\u001c-\u001f]+$/gu, '');
    const length = Array.from(text).length;
    $('[data-comment-count]').textContent = `${length} / 100`;
    textarea.setAttribute('aria-invalid', String(length > 100));
    form.querySelector('[type=submit]').disabled = pending || !user || length < 1 || length > 100;
  }
  function account() {
    const target = $('[data-account]'); target.replaceChildren();
    $('[data-guest]').hidden = Boolean(user); form.hidden = !user;
    if (user) {
      const name = document.createElement('span'); name.textContent = user.username;
      target.append(name, button('退出', logout));
    } else target.append(button('登录', () => openAuth('login')));
    count();
  }
  async function request(path, data) {
    const response = await fetch(api + path, {
      method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: data === undefined ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf || '' },
      body: data === undefined ? undefined : JSON.stringify(data), signal: AbortSignal.timeout(15000)
    });
    let payload;
    try { payload = await response.json(); } catch { throw new Error('评论服务暂时不可用，请稍后重试。'); }
    if (!response.ok) {
      if (response.status === 401 && !['login', 'register'].includes(path)) {
        revision++; user = null; csrf = null; account();
        list.querySelectorAll('[data-delete]').forEach(node => node.remove());
      }
      throw new Error(payload.error || '操作失败，请稍后重试。');
    }
    return payload;
  }
  const errorText = error => ['TypeError', 'TimeoutError', 'AbortError'].includes(error.name) ? '连接失败，请稍后重试。' : error.message;
  function renderItem(item) {
    const entry = document.createElement('article'); entry.className = 'comment-entry'; entry.dataset.id = item.id;
    const meta = document.createElement('div'); meta.className = 'comment-meta';
    const name = document.createElement('h3'); name.textContent = item.author;
    const time = document.createElement('time'); time.dateTime = item.created;
    time.textContent = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(item.created));
    meta.append(name, time);
    if (item.mine && user) {
      const remove = button('删除', () => { selected = entry; $('[data-delete-status]').textContent = ''; deleteDialog.showModal(); });
      remove.dataset.delete = ''; meta.append(remove);
    }
    const text = document.createElement('p'); text.textContent = item.text;
    entry.append(meta, text); return entry;
  }
  async function load(more = false) {
    if (more && pending) return false;
    const current = ++loadId, version = revision, feedback = feedbackId;
    $('[data-more]').disabled = true;
    try {
      const query = `comments?article=${encodeURIComponent(article)}${more && next ? `&before=${next}` : ''}`;
      const payload = await request(query);
      if (current !== loadId || version !== revision) return false;
      if (!more) list.replaceChildren();
      for (const item of payload.comments) {
        if (!list.querySelector(`[data-id="${item.id}"]`)) list.append(renderItem(item));
      }
      next = payload.next; $('[data-more]').hidden = !next;
      $('[data-empty]').hidden = Boolean(list.childElementCount);
      $('[data-retry]').hidden = true;
      if (feedback === feedbackId) message();
      return true;
    } catch (error) {
      if (current !== loadId || version !== revision) return false;
      message(errorText(error), true); $('[data-retry]').hidden = false;
      return false;
    } finally { if (current === loadId) $('[data-more]').disabled = false; }
  }
  async function initialize() {
    const current = ++initializationId, version = revision;
    $('[data-retry]').hidden = true;
    try {
      const payload = await request('session');
      if (current !== initializationId || version !== revision) return;
      user = payload.user; csrf = payload.csrf;
      account(); await load();
    } catch (error) { if (current === initializationId && version === revision) { message(errorText(error), true); $('[data-retry]').hidden = false; } }
  }
  function openAuth(value) {
    if (pending || authPending) return;
    mode = value; const registering = mode === 'register';
    $('#reader-title').textContent = registering ? '创建账号' : '登录';
    $('[data-auth-submit]').textContent = registering ? '注册并登录' : '登录';
    $('[data-mode]').textContent = registering ? '已有账号' : '创建账号';
    $('[data-confirm]').hidden = !registering;
    $('[name=confirm]').required = registering;
    $('[data-register-note]').hidden = !registering;
    $('[name=password]').autocomplete = registering ? 'new-password' : 'current-password';
    $('[data-auth-status]').textContent = '';
    if (!auth.open) auth.showModal();
  }
  $('[data-mode]').addEventListener('click', () => openAuth(mode === 'login' ? 'register' : 'login'));
  $('[data-close]').addEventListener('click', () => auth.close());
  auth.addEventListener('close', () => { $('[name=password]').value = ''; $('[name=confirm]').value = ''; });
  authForm.addEventListener('submit', async event => {
    event.preventDefault(); if (authPending) return;
    const username = $('[name=username]').value, password = $('[name=password]').value;
    const passwordLength = Array.from(password).length;
    if (mode === 'register' && (passwordLength < 12 || passwordLength > 128 || password !== $('[name=confirm]').value)) {
      $('[data-auth-status]').textContent = '密码需为 12–128 个字符，且两次输入需一致。'; return;
    }
    authPending = true;
    authForm.querySelectorAll('button').forEach(node => node.disabled = true);
    $('[data-auth-status]').textContent = mode === 'register' ? '正在创建账号…' : '正在登录…';
    try {
      const payload = await request(mode, { username, password });
      revision++; user = payload.user; csrf = payload.csrf; account(); auth.close(); authPending = false; await load();
    } catch (error) { $('[data-auth-status]').textContent = errorText(error); }
    finally { authPending = false; authForm.querySelectorAll('button').forEach(node => node.disabled = false); }
  });
  async function logout() {
    if (pending || authPending) return; pending = true; count();
    try { await request('logout', {}); revision++; user = null; csrf = null; account(); await load(); }
    catch (error) { message(errorText(error), true); }
    finally { pending = false; count(); }
  }
  textarea.addEventListener('input', count);
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (pending || !user || form.querySelector('[type=submit]').disabled) return;
    pending = true; count(); const text = textarea.value;
    message('正在发布…');
    try {
      const item = await request('comments', { article, text });
      revision++;
      list.prepend(renderItem(item)); $('[data-empty]').hidden = true;
      if (textarea.value === text) textarea.value = '';
      message('评论已发布。');
      const refreshed = await load();
      message(refreshed ? '评论已发布。' : '评论已发布，暂时无法刷新其他评论。', !refreshed);
    } catch (error) { message(errorText(error), true); }
    finally { pending = false; count(); }
  });
  $('[data-cancel-delete]').addEventListener('click', () => deleteDialog.close());
  $('[data-confirm-delete]').addEventListener('click', async () => {
    if (!selected || pending) return; pending = true;
    const entry = selected; const confirm = $('[data-confirm-delete]'); confirm.disabled = true;
    try {
      await request(`comments/${entry.dataset.id}/delete`, {});
      revision++;
      entry.remove(); deleteDialog.close(); $('[data-empty]').hidden = Boolean(list.childElementCount);
      const refreshed = await load();
      message(refreshed ? '评论已删除。' : '评论已删除，暂时无法刷新其他评论。', !refreshed);
    } catch (error) { $('[data-delete-status]').textContent = errorText(error); }
    finally { pending = false; confirm.disabled = false; count(); }
  });
  $('[data-more]').addEventListener('click', () => load(true));
  $('[data-retry]').addEventListener('click', initialize);
  window.addEventListener('pageshow', event => { if (event.persisted) initialize(); });
  initialize();
})();
