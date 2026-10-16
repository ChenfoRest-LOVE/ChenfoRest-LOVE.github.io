(() => {
  'use strict';
  const form = document.getElementById('album-password-form');
  const grid = document.getElementById('photo-grid');
  if (!form || !grid || grid.dataset.protected !== 'true') return;
  const input = form.querySelector('input');
  const submit = form.querySelector('button');
  const status = document.getElementById('album-lock-status');
  const urls = [];
  const decode = text => {
    if (typeof text !== 'string' || text.length > 52 * 1024 * 1024 || !/^[A-Za-z0-9+/]*={0,2}$/.test(text)) throw new Error('invalid');
    return Uint8Array.from(atob(text), char => char.charCodeAt(0));
  };
  if (!window.isSecureContext || !window.crypto?.subtle) {
    status.textContent = '请通过 HTTPS 或本机预览打开此相册。';
    return;
  }
  input.disabled = false; submit.disabled = false;
  let busy = false;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    busy = true; submit.disabled = true; status.textContent = '正在解锁…';
    let envelope;
    try {
      const expected = `private/${grid.dataset.album}.enc.json`;
      if (grid.dataset.payload !== expected) throw new Error('invalid');
      const response = await fetch(expected, {credentials:'omit', cache:'no-store', signal:AbortSignal.timeout(20000)});
      if (!response.ok || Number(response.headers.get('Content-Length')) > 52 * 1024 * 1024) throw new Error('download');
      const raw = await response.text();
      if (raw.length > 52 * 1024 * 1024) throw new Error('download');
      envelope = JSON.parse(raw);
    } catch {
      input.value = ''; status.textContent = '加密文件加载失败，请稍后重试。'; busy = false; submit.disabled = false; return;
    }
    try {
      if (envelope.format !== 'forest-album-v1' || envelope.album !== grid.dataset.album || envelope.iterations !== 600000) throw new Error('invalid');
      const salt = decode(envelope.salt), iv = decode(envelope.iv);
      if (salt.length !== 16 || iv.length !== 12) throw new Error('invalid');
      const material = await crypto.subtle.importKey('raw', new TextEncoder().encode(input.value), 'PBKDF2', false, ['deriveKey']);
      input.value = '';
      const key = await crypto.subtle.deriveKey({name:'PBKDF2', hash:'SHA-256', salt, iterations:600000}, material, {name:'AES-GCM', length:256}, false, ['decrypt']);
      const plaintext = await crypto.subtle.decrypt({name:'AES-GCM', iv, tagLength:128, additionalData:new TextEncoder().encode('forest-album-v1:' + grid.dataset.album)}, key, decode(envelope.ciphertext));
      const data = JSON.parse(new TextDecoder('utf-8', {fatal:true}).decode(plaintext));
      if (data.album?.id !== grid.dataset.album || !Array.isArray(data.photos) || !data.photos.length || !data.files) throw new Error('invalid');
      const imageUrl = file => {
        const match = /^images\/[a-z0-9-]+\.(webp|jpg|jpeg|png)$/.exec(file);
        if (!match) throw new Error('invalid');
        const mime = {webp:'image/webp', jpg:'image/jpeg', jpeg:'image/jpeg', png:'image/png'}[match[1]];
        const url = URL.createObjectURL(new Blob([decode(data.files[file])], {type:mime})); urls.push(url); return url;
      };
      const photos = data.photos.map(photo => {
        if (photo.category !== grid.dataset.album || typeof photo.alt !== 'string' || typeof photo.caption !== 'string' || !['width','height'].every(k => Number.isInteger(photo[k]) && photo[k] > 0 && photo[k] <= 20000)) throw new Error('invalid');
        return {...photo, src:imageUrl(photo.file), thumbnail:imageUrl(photo.thumbnail)};
      });
      grid.hidden = false; document.getElementById('photo-status').hidden = false;
      document.getElementById('private-toolbar').hidden = false;
      window.initPhotoGallery(photos);
      document.getElementById('album-lock').hidden = true;
      document.getElementById('album-relock').focus({preventScroll:true});
    } catch {
      input.value = ''; urls.splice(0).forEach(url => URL.revokeObjectURL(url));
      status.textContent = '密码不正确，或加密文件已损坏。'; submit.disabled = false; input.focus();
    } finally { busy = false; }
  });
  document.getElementById('album-relock').addEventListener('click', () => location.reload());
  window.addEventListener('pagehide', () => urls.splice(0).forEach(url => URL.revokeObjectURL(url)));
  window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
})();
