(() => {
  'use strict';
  if (location.hostname !== '127.0.0.1' || location.protocol !== 'http:') return;
  const form = document.getElementById('setup-form'), status = document.getElementById('status');
  let csrf = '';
  const message = (text, error = false) => { status.textContent = text; status.classList.toggle('error', error); };
  fetch('/state', {cache: 'no-store', credentials: 'same-origin'}).then(async response => {
    const data = await response.json(); if (!response.ok) throw new Error(data.error);
    csrf = data.csrf; form.querySelectorAll('input,button').forEach(el => el.disabled = false); message('密码仅发送到你的服务器，不会经过聊天或 GitHub。');
  }).catch(error => message(error.message || '连接失败，请刷新。', true));
  form.addEventListener('submit', async event => {
    event.preventDefault(); const button = form.querySelector('button'); button.disabled = true; message('正在创建…');
    try {
      const data = Object.fromEntries(new FormData(form));
      const response = await fetch('/setup', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify(data)});
      const result = await response.json(); if (!response.ok) throw new Error(result.error || '设置失败。');
      form.reset(); form.hidden = true; message('管理员已创建，此设置入口已关闭。公网域名恢复访问后，可在 denss.asia/admin/ 登录。');
    } catch (error) { message(error.message || '连接失败，请重试。', true); button.disabled = false; }
  });
})();
