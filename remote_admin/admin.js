(() => {
  'use strict';
  // A copy served by GitHub Pages must never collect credentials on that origin.
  if (location.origin !== 'https://denss.asia') { location.replace('https://denss.asia/admin/'); return; }
  const $ = id => document.getElementById(id);
  const status = (message, error = false) => { $('status').textContent = message; $('status').classList.toggle('error', error); };
  let csrf = '';
  async function api(path, data) {
    const response = await fetch('/api/admin/' + path, {method: data ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: data ? {'Content-Type': 'application/json', 'X-CSRF-Token': csrf} : {}, ...(data ? {body: JSON.stringify(data)} : {})});
    const body = await response.json();
    if (!response.ok) { const error = new Error(body.error || '请求失败，请稍后重试。'); error.status = response.status; throw error; }
    return body;
  }
  function showLogin() { csrf = ''; $('management-panel').hidden = true; $('albums').replaceChildren(); $('login-panel').hidden = false; $('login-form').querySelectorAll('input,button').forEach(el => el.disabled = false); }
  function render(data) {
    csrf = data.csrf; $('login-panel').hidden = true; $('management-panel').hidden = false;
    $('albums').replaceChildren();
    for (const album of data.albums) {
      const section = document.createElement('section'); section.className = 'album'; section.dataset.album = album.id;
      const heading = document.createElement('div'); heading.className = 'album-title';
      const title = document.createElement('h2'); title.textContent = album.title;
      const english = document.createElement('small'); english.textContent = album.english; heading.append(title, english);
      const choices = document.createElement('div'); choices.className = 'choices';
      if (album.protected) {
        const note = document.createElement('p'); note.className = 'hint'; note.textContent = '密码保护中，封面保持模糊。密码设置请在本机 GitHub 管理入口处理。';
        section.append(heading, note); $('albums').append(section); continue;
      }
      const photos = data.photos.filter(photo => photo.category === album.id);
      for (const [i, photo] of photos.entries()) {
        if (!/^images\/[a-z0-9-]+\.(webp|jpg|jpeg|png)$/.test(photo.thumbnail || photo.file)) continue;
        const figure = document.createElement('figure'); figure.className = 'choice'; figure.dataset.selected = String(album.cover === photo.file);
        const image = document.createElement('img'); image.src = '/content/photos/' + (photo.thumbnail || photo.file); image.alt = photo.alt; image.loading = 'lazy';
        const caption = document.createElement('figcaption'); const number = document.createElement('span'); number.textContent = String(i + 1).padStart(2, '0');
        const button = document.createElement('button'); button.type = 'button'; button.disabled = album.cover === photo.file; button.textContent = button.disabled ? '当前封面' : '设为封面'; button.setAttribute('aria-label', button.textContent + '：' + photo.alt);
        button.addEventListener('click', async () => {
          document.querySelectorAll('.choice button').forEach(el => el.disabled = true); status('正在保存…');
          try { await api('cover', {album: album.id, file: photo.file}); await load(); status('已保存。两个站点将在下次打开影像页时读取新封面。'); }
          catch (error) { if (error.status === 401) showLogin(); else { try { await load(); } catch {} } status(error.message, true); }
        });
        caption.append(number, button); figure.append(image, caption); choices.append(figure);
      }
      section.append(heading, choices); $('albums').append(section);
    }
  }
  async function load() { render(await api('state')); }
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault(); $('login-submit').disabled = true; status('正在登录…');
    const password = $('password').value;
    try { await api('login', {username: $('username').value, password}); $('password').value = ''; await load(); status('已登录。'); }
    catch (error) { $('password').value = ''; showLogin(); status(error.message, true); }
  });
  $('logout').addEventListener('click', async () => {
    $('logout').disabled = true;
    try { await api('logout', {}); showLogin(); status('已退出登录。'); }
    catch (error) { status(error.message, true); }
    finally { $('logout').disabled = false; }
  });
  load().then(() => status('')).catch(error => { showLogin(); status(error.status === 401 ? '仅限网站所有者。' : '暂时无法连接管理服务，请稍后重试。', error.status !== 401); });
})();
