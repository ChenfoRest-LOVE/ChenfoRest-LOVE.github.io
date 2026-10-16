(() => {
  'use strict';
  const links = [...document.querySelectorAll('.album-link[data-album]')];
  if (!links.length) return;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  const endpoint = ['denss.asia', 'www.denss.asia'].includes(location.hostname) ? '/api/covers' : 'https://denss.asia/api/covers';
  Promise.all([
    fetch(endpoint, {credentials:'omit', cache:'no-store', signal:controller.signal}),
    fetch('content/photos/index.json', {credentials:'omit', signal:controller.signal})
  ]).then(async responses => {
    if (responses.some(response => !response.ok)) throw new Error('unavailable');
    const [settings, photos] = await Promise.all(responses.map(response => response.json()));
    if (!settings.covers || !Array.isArray(photos)) return;
    for (const link of links) {
      const photo = photos.find(item => item.category === link.dataset.album && item.file === settings.covers[link.dataset.album]);
      if (!photo || !/^images\/[a-z0-9-]+\.(webp|jpg|jpeg|png)$/.test(photo.thumbnail || photo.file)) continue;
      const image = link.querySelector('img');
      if (image) {
        const preview = new Image();
        preview.onload = () => { image.src = preview.src; image.alt = photo.alt; image.width = photo.width; image.height = photo.height; };
        preview.src = 'content/photos/' + (photo.thumbnail || photo.file);
      }
    }
  }).catch(() => { /* The versioned static covers remain visible when the CMS is offline. */ }).finally(() => clearTimeout(timeout));
})();
