'use strict';

(async () => {
  const response = await fetch('/_manage/state', {credentials:'same-origin',cache:'no-store'});
  if (!response.ok) return;
  let state = await response.json();
  let busy = false;
  let retry = null;
  function node(tag, className, text) {
    const item = document.createElement(tag);
    item.className = className;
    if (text) item.textContent = text;
    return item;
  }
  const style = node('style','');
  style.textContent = '.manager-bar{margin:0 0 30px;padding:14px 0;border-bottom:1px solid var(--line);font-size:11px;color:var(--muted);display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 18px}.manager-bar strong{color:var(--ink);font-weight:400;letter-spacing:.08em}.manager-status{flex-basis:100%;overflow-wrap:anywhere}.manager-status:empty{display:none}.manager-status[data-error=true]{color:var(--accent)}.manager-action,.set-cover{padding:5px 10px;border:1px solid var(--line);font-size:11px;color:var(--muted);line-height:1.7}.manager-action:hover,.set-cover:hover{border-color:var(--accent);color:var(--ink)}.set-cover[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}.set-cover:disabled,.manager-action:disabled{opacity:.5;cursor:wait}.album-page .photo-grid figcaption{align-items:center}.manager-action{margin-left:auto}';
  document.head.append(style);
  const bar = node('aside','manager-bar');
  bar.setAttribute('aria-label','封面管理');
  bar.append(node('strong','','封面管理 · 仅本机'),node('span','','更换后发布到全站。'));
  const sync = node('button','manager-action','同步当前封面');
  sync.type = 'button';
  const status = node('p','manager-status');
  status.setAttribute('role','status');
  status.setAttribute('aria-live','polite');
  bar.append(sync,status);
  document.querySelector('main').prepend(bar);

  function refreshButtons() {
    document.querySelectorAll('.set-cover').forEach(button => {
      const album = state.albums.find(a => a.id === button.dataset.album);
      const current = album?.cover === button.dataset.file;
      button.textContent = current ? '当前封面' : '设为封面';
      button.setAttribute('aria-pressed',String(current));
      button.disabled = busy;
      button.title = current ? '可重新同步当前封面' : '将此照片设为图册封面并发布';
    });
    sync.disabled = busy;
  }
  async function publish(choice) {
    if (busy || !choice) return;
    busy = true;
    retry = choice;
    status.dataset.error = 'false';
    status.textContent = '正在保存并发布，请稍候…';
    sync.textContent = '发布中…';
    refreshButtons();
    try {
      const result = await fetch('/_manage/cover',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(choice)});
      const data = await result.json();
      if (!result.ok) throw new Error(data.error || '发布未完成，请重试。');
      const fresh = await fetch('/_manage/state',{credentials:'same-origin',cache:'no-store'});
      if (fresh.ok) state = await fresh.json();
      status.textContent = data.message || '封面已发布。';
      sync.textContent = '同步当前封面';
      retry = null;
    } catch (error) {
      status.dataset.error = 'true';
      status.textContent = error instanceof TypeError ? '本机管理连接中断，可重新打开管理入口后重试。' : error.message;
      sync.textContent = '重试发布';
    } finally {
      busy = false;
      refreshButtons();
    }
  }
  const grid = document.querySelector('#photo-grid');
  function addButtons() {
    if (!grid) return;
    grid.querySelectorAll('figure').forEach(figure => {
      if (figure.querySelector('.set-cover')) return;
      const file = figure.querySelector('.photo-media')?.dataset.photoFile;
      const photo = state.photos.find(p => p.file === file && p.category === grid.dataset.album);
      if (!photo) return;
      const button = node('button','set-cover');
      button.type = 'button';
      button.dataset.file = file;
      button.dataset.album = photo.category;
      button.addEventListener('click',() => publish({album:photo.category,file}));
      figure.querySelector('figcaption').append(button);
    });
    refreshButtons();
  }
  if (grid) {
    new MutationObserver(addButtons).observe(grid,{childList:true});
    addButtons();
  }
  sync.addEventListener('click',() => {
    const album = state.albums.find(a => a.id === grid?.dataset.album) || state.albums[0];
    publish(retry || (album && {album:album.id,file:album.cover}));
  });
})().catch(() => { /* Management capability is never required for public reading. */ });
