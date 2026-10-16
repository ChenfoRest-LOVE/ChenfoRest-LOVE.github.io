(() => {
  'use strict';
  const node = (tag, text, className = '') => { const el = document.createElement(tag); if (text) el.textContent = text; el.className = className; return el; };
  const style = node('style');
  style.textContent = '.album-manager-entry{min-width:0}.privacy-open{font-size:11px;color:var(--muted);padding:0 0 18px;display:inline-flex;gap:8px;align-items:center}.privacy-open:hover{color:var(--ink)}.privacy-dialog{width:min(480px,calc(100% - 36px));max-height:90svh;overflow:auto;background:var(--bg);color:var(--ink);border:1px solid var(--line);padding:30px}.privacy-dialog::backdrop{background:rgba(0,0,0,.75);backdrop-filter:blur(5px)}.privacy-dialog h2{font:400 25px/1.5 var(--serif);letter-spacing:.05em}.privacy-dialog form{display:flex;flex-direction:column;gap:11px}.privacy-dialog label{font-size:11px;color:var(--muted);margin-top:8px}.privacy-dialog input,.privacy-dialog select{background:var(--surface);border:1px solid var(--line);border-radius:0;color:var(--ink);padding:10px 12px;font:inherit;font-size:14px;min-width:0;width:100%;min-height:43px}.privacy-dialog .privacy-hint{font-size:11px;line-height:1.9;color:var(--muted);margin:18px 0}.privacy-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}.privacy-actions button{font-size:12px;border:1px solid var(--line);padding:10px 14px}.privacy-actions button:hover{border-color:var(--accent)}.privacy-actions button:disabled{opacity:.5;cursor:wait}.privacy-feedback{font-size:12px;line-height:1.8;color:var(--muted);min-height:22px}.privacy-heading{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:18px}.privacy-close{font-size:22px;color:var(--muted);padding:0 5px}.privacy-dialog [hidden]{display:none!important}';
  document.head.append(style);
  let state, busy = false, trigger;
  const dialog = node('dialog', '', 'privacy-dialog'); dialog.setAttribute('aria-labelledby', 'privacy-title');
  const heading = node('div', '', 'privacy-heading'), title = node('h2'); title.id = 'privacy-title';
  const close = node('button', '×', 'privacy-close'); close.type = 'button'; close.setAttribute('aria-label', '关闭密码设置'); heading.append(title, close);
  const form = node('form');
  const modeLabel = node('label', '操作'); modeLabel.htmlFor = 'privacy-mode';
  const mode = node('select'); mode.id = 'privacy-mode';
  const field = (id, label, autocomplete) => {
    const wrapper = node('div'), caption = node('label', label), input = node('input');
    caption.htmlFor = id; input.id = id; input.type = 'password'; input.autocomplete = autocomplete; input.maxLength = 128;
    wrapper.append(caption, input); return {wrapper, input};
  };
  const old = field('privacy-old', '当前相册密码', 'current-password');
  const password = field('privacy-new', '新相册密码（至少 14 位）', 'new-password'); password.input.minLength = 14;
  const confirm = field('privacy-confirm', '确认新密码', 'new-password'); confirm.input.minLength = 14;
  const hint = node('p', '密码只用于本机加密，不保存到 GitHub。请自行保管密码；只保护当前版本。旧密码仍能解锁 Git 历史密文，历史原图、旧服务器和缓存副本也可能继续访问。模糊封面会保留大致颜色与轮廓。', 'privacy-hint');
  const actions = node('div', '', 'privacy-actions'), save = node('button', '保存并发布 GitHub'), cancel = node('button', '取消'); save.type = 'submit'; cancel.type = 'button'; actions.append(save, cancel);
  const feedback = node('p', '', 'privacy-feedback'); feedback.setAttribute('role', 'status'); feedback.setAttribute('aria-live', 'polite');
  const retry = node('button', '重试推送 GitHub'); retry.type = 'button'; retry.title = '仅推送已保存的提交，不重新设置密码。'; actions.append(retry);
  form.append(modeLabel, mode, old.wrapper, password.wrapper, confirm.wrapper, hint, actions, feedback); dialog.append(heading, form); document.body.append(dialog);
  let current;
  function setFields() {
    const unlocking = mode.value === 'unlock';
    old.wrapper.hidden = !current.protected; old.input.required = !!current.protected;
    password.wrapper.hidden = unlocking; confirm.wrapper.hidden = unlocking;
    password.input.required = confirm.input.required = !unlocking;
    old.input.disabled = !current.protected; password.input.disabled = confirm.input.disabled = unlocking;
    save.textContent = unlocking ? '取消保护并发布 GitHub' : '保存并发布 GitHub';
    if (unlocking) hint.textContent = '取消保护后，照片会作为公开文件提交 GitHub，任何人均可查看。';
    else hint.textContent = '密码只用于本机加密，不保存到 GitHub。请自行保管密码；只保护当前版本。旧密码仍能解锁 Git 历史密文，历史原图、旧服务器和缓存副本也可能继续访问。模糊封面会保留大致颜色与轮廓。';
  }
  function open(album, button) {
    current = album; trigger = button; form.reset(); feedback.textContent = '';
    title.textContent = album.title + ' · 密码设置'; mode.replaceChildren();
    for (const [value, text] of album.protected ? [['password','修改密码'], ['unlock','取消密码保护']] : [['lock','设置密码']]) {
      const option = node('option', text); option.value = value; mode.append(option);
    }
    setFields(); dialog.showModal(); (album.protected ? old.input : password.input).focus();
  }
  function closeDialog() { if (!busy) dialog.close(); }
  close.addEventListener('click', closeDialog); cancel.addEventListener('click', closeDialog);
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  dialog.addEventListener('close', () => { form.reset(); trigger?.focus({preventScroll:true}); });
  mode.addEventListener('change', setFields);
  async function send(path, data) {
    const response = await fetch('/_manage/' + path, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf}, body:JSON.stringify(data)});
    const result = await response.json(); if (!response.ok) { const error = new Error(result.error || '发布未完成。'); error.step = result.step; throw error; } return result;
  }
  async function perform(path, data) {
    busy = true; save.disabled = cancel.disabled = close.disabled = retry.disabled = true; feedback.textContent = '正在保存并发布，请稍候…';
    try { const result = await send(path, data); feedback.textContent = result.message; setTimeout(() => location.reload(), 900); }
    catch (error) { feedback.textContent = error.message || '本机连接中断，请重试。'; }
    finally { old.input.value = password.input.value = confirm.input.value = ''; busy = false; save.disabled = cancel.disabled = close.disabled = retry.disabled = false; }
  }
  form.addEventListener('submit', event => {
    event.preventDefault(); if (busy) return;
    const action = mode.value;
    if (action !== 'unlock' && password.input.value !== confirm.input.value) { feedback.textContent = '两次输入的密码不一致。'; return; }
    perform('privacy', {album:current.id, action, password:action === 'lock' ? password.input.value : old.input.value, newPassword:password.input.value, confirm:confirm.input.value});
  });
  retry.addEventListener('click', () => { if (!busy) perform('publish', {}); });
  fetch('/_manage/state', {credentials:'same-origin', cache:'no-store'}).then(async response => {
    if (!response.ok) return; state = await response.json();
    const grid = document.getElementById('photo-grid');
    for (const album of state.albums) {
      let parent;
      const link = document.querySelector(`.album-link[data-album="${album.id}"]`);
      if (link) { parent = node('div', '', 'album-manager-entry'); link.replaceWith(parent); parent.append(link); }
      else if (grid?.dataset.album === album.id) parent = document.querySelector('main .module-heading');
      if (!parent) continue;
      const button = node('button', album.protected ? '管理相册密码' : '设置相册密码', 'privacy-open'); button.type = 'button'; button.setAttribute('aria-label', album.title + '：' + button.textContent);
      button.addEventListener('click', () => open(album, button)); parent.append(button);
    }
  }).catch(() => {});
})();
