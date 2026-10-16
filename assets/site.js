'use strict';

const quotes = [
  { text: 'Ὁ δὲ ἀνεξέταστος βίος οὐ βιωτὸς ἀνθρώπῳ.', source: 'Plato · Apology' },
  { text: 'Cogito, ergo sum.', source: 'René Descartes · Principia Philosophiae' },
  { text: 'Was mich nicht umbringt, macht mich stärker.', source: 'Friedrich Nietzsche · Götzen-Dämmerung' },
  { text: 'Je pense, donc je suis.', source: 'René Descartes · Discours de la méthode' },
  { text: 'Ὅτι οὐ τὰ πράγματα ταράσσει τοὺς ἀνθρώπους, ἀλλὰ τὰ περὶ τῶν πραγμάτων δόγματα.', source: 'Epictetus · Enchiridion' }
];
let quoteIndex = 0;
document.querySelector('#quote button')?.addEventListener('click', () => {
  quoteIndex = (quoteIndex + 1) % quotes.length;
  document.querySelector('#quote p').textContent = quotes[quoteIndex].text;
  document.querySelector('#quote cite').textContent = quotes[quoteIndex].source;
});

const themeToggle = document.querySelector('.theme-toggle');
function setTheme(theme) {
  const dark = theme !== 'light';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  themeToggle.setAttribute('aria-pressed', String(dark));
  themeToggle.setAttribute('aria-label', dark ? '切换浅色模式' : '切换深色模式');
  document.querySelector('meta[name="theme-color"]').content = dark ? '#141713' : '#eeeee6';
  try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch { /* Storage can be unavailable in private or restricted contexts. */ }
}
let initialTheme = 'dark';
try { if (localStorage.getItem('theme') === 'light') initialTheme = 'light'; } catch { /* Use the default dark theme. */ }
setTheme(initialTheme);
themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

const menuToggle = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#main-nav');
function setMenu(open, returnFocus = false) {
  menuToggle.setAttribute('aria-expanded', String(open));
  menuToggle.setAttribute('aria-label', open ? '收起导航' : '展开导航');
  navigation.classList.toggle('is-open', open);
  if (open) navigation.querySelector('a').focus();
  if (returnFocus) menuToggle.focus();
}
menuToggle.addEventListener('click', () => setMenu(menuToggle.getAttribute('aria-expanded') !== 'true'));
navigation.addEventListener('click', event => { if (event.target.closest('a')) setMenu(false); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') setMenu(false, true);
});
document.addEventListener('click', event => {
  if (!event.target.closest('.header')) setMenu(false);
});
window.matchMedia('(min-width: 601px)').addEventListener('change', event => { if (event.matches) setMenu(false); });

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let revealObserver;
if ('IntersectionObserver' in window && !reducedMotion.matches) {
  document.documentElement.classList.add('reveal-ready');
  revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: .08, rootMargin: '0px 0px -25px 0px' });
}
function revealElements(root = document) {
  root.querySelectorAll('.reveal').forEach(element => {
    if (revealObserver) revealObserver.observe(element);
  });
}
revealElements();
let scrollFrame = 0;
const hero = document.querySelector('.hero');
function updateDepth() {
  scrollFrame = 0;
  if (!hero) return;
  hero.style.setProperty('--hero-offset', reducedMotion.matches ? '0px' : `${Math.min(window.scrollY * .12, 80)}px`);
}
window.addEventListener('scroll', () => {
  if (hero && !scrollFrame && window.scrollY < hero.offsetHeight + 100) scrollFrame = requestAnimationFrame(updateDepth);
}, { passive: true });
reducedMotion.addEventListener('change', () => {
  updateDepth();
  if (reducedMotion.matches) {
    document.documentElement.classList.remove('reveal-ready');
    if (revealObserver) revealObserver.disconnect();
    revealObserver = undefined;
  }
});
updateDepth();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Resolve only local files inside the intended content directory.
function localContentPath(directory, file, extensions) {
  if (typeof file !== 'string' || !file.trim() || /[\\?#\u0000-\u001f]/.test(file) || file.startsWith('/') || /^[a-z][a-z\d+.-]*:/i.test(file)) return null;
  try {
    const parts = file.split('/').map(part => decodeURIComponent(part));
    if (parts.some(part => !part || part === '.' || part === '..' || /[\\/%?#\u0000-\u001f]/.test(part))) return null;
    const base = new URL(directory, document.baseURI);
    const url = new URL(file, base);
    if (url.origin !== location.origin || !url.pathname.startsWith(base.pathname) || !extensions.test(url.pathname)) return null;
    return url.href;
  } catch { return null; }
}
async function readIndex(path) {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-cache' });
  if (!response.ok) throw new Error('Content unavailable');
  const data = await response.json();
  if (!Array.isArray(data)) throw new Error('Invalid content index');
  return data;
}
function showWritingEmpty(container, failed = false) {
  const row = element('div', 'writing-empty');
  const mark = element('span', '', '—');
  mark.setAttribute('aria-hidden', 'true');
  const copy = element('div');
  copy.append(element('h3', '', failed ? '文字加载失败。' : '暂无公开条目。'));
  copy.append(element('p', '', failed ? '刷新页面重试。' : '随笔与阅读记录。'));
  row.append(mark, copy, element('small', '', failed ? 'LOAD FAILED' : 'NO ENTRIES'));
  container.replaceChildren(row);
}
async function hydrateWriting() {
  const container = document.querySelector('#writing-list');
  try {
    const data = await readIndex('content/writing/index.json');
    if (!data.length) { showWritingEmpty(container); return; }
    const fragment = document.createDocumentFragment();
    let invalid = 0;
    data.forEach(item => {
      if (!item || typeof item.title !== 'string' || typeof item.date !== 'string') { invalid++; return; }
      const href = localContentPath('content/writing/', item.file, /\.(?:html?|md|pdf|txt)$/i);
      if (!href) { invalid++; return; }
      const link = element('a', 'writing-entry');
      link.href = href;
      const heading = element('h2', '', item.title);
      const time = element('time', '', item.date.replaceAll('-', '.'));
      if (/^\d{4}-\d{2}-\d{2}$/.test(item.date)) time.dateTime = item.date;
      link.append(heading, time);
      fragment.append(link);
    });
    container.replaceChildren(fragment);
    if (invalid) container.append(element('p', 'content-status', '部分文章条目信息不完整，暂时无法显示。'));
  } catch { showWritingEmpty(container, true); }
}

function initPhotoGallery() {
  let photos = [];
  let visiblePhotos = [];
  let activeFilter = 'all';
  let lightboxIndex = 0;
  let lightboxTrigger;
  const photoGrid = document.querySelector('#photo-grid');
  const photoStatus = document.querySelector('#photo-status');
  const lightbox = document.querySelector('.lightbox');
  const lightboxImage = document.querySelector('#lightbox-image');
  const lightboxStatus = element('p', 'lightbox-status');
  lightboxStatus.setAttribute('role', 'status');
  lightboxStatus.setAttribute('aria-live', 'polite');
  lightboxStatus.setAttribute('aria-atomic', 'true');
  lightboxImage.before(lightboxStatus);
  const lightboxCaption = document.querySelector('#lightbox-caption');
  const lightboxCounter = document.querySelector('#lightbox-counter');
  const previousButton = document.querySelector('.lightbox-prev');
  const nextButton = document.querySelector('.lightbox-next');
  let photoLoadWarning = '';

  lightboxImage.addEventListener('load', () => {
    lightboxStatus.textContent = '';
    lightboxImage.hidden = false;
  });
  lightboxImage.addEventListener('error', () => {
    lightboxImage.hidden = true;
    lightboxStatus.textContent = '影像暂时无法加载。可切换至其他影像，或关闭预览后重试。';
  });

  function showLightboxPhoto() {
    const photo = visiblePhotos[lightboxIndex];
    if (!photo) return;
    lightboxImage.hidden = true;
    lightboxStatus.textContent = '正在加载影像…';
    lightboxImage.alt = photo.alt;
    lightboxImage.width = photo.width;
    lightboxImage.height = photo.height;
    lightboxImage.src = photo.src;
    lightboxCaption.textContent = [photo.caption, photo.credit].filter(Boolean).join(' · ');
    lightboxCounter.textContent = `${String(lightboxIndex + 1).padStart(2, '0')} / ${String(visiblePhotos.length).padStart(2, '0')}`;
    previousButton.disabled = nextButton.disabled = visiblePhotos.length < 2;
  }
  function openLightbox(index, trigger) {
    lightboxIndex = index;
    lightboxTrigger = trigger;
    showLightboxPhoto();
    lightbox.showModal();
    document.body.classList.add('dialog-open');
    document.querySelector('.lightbox-close').focus();
  }
  function stepLightbox(direction) {
    if (!visiblePhotos.length) return;
    lightboxIndex = (lightboxIndex + direction + visiblePhotos.length) % visiblePhotos.length;
    showLightboxPhoto();
  }
  document.querySelector('.lightbox-close').addEventListener('click', () => lightbox.close());
  previousButton.addEventListener('click', () => stepLightbox(-1));
  nextButton.addEventListener('click', () => stepLightbox(1));
  lightbox.addEventListener('click', event => { if (event.target === lightbox) lightbox.close(); });
  lightbox.addEventListener('close', () => {
    document.body.classList.remove('dialog-open');
    if (lightboxTrigger && lightboxTrigger.isConnected) lightboxTrigger.focus({ preventScroll: true });
  });
  lightbox.addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      stepLightbox(event.key === 'ArrowLeft' ? -1 : 1);
    }
  });

  function renderPhotos(announce = false) {
    visiblePhotos = photos.filter(photo => activeFilter === 'all' || photo.category === activeFilter);
    const fragment = document.createDocumentFragment();
    visiblePhotos.forEach((photo, index) => {
      const figure = element('figure', 'reveal');
      figure.style.setProperty('--photo-width', `${Math.min(photo.width, 1100)}px`);
      const button = element('button', 'photo-media');
      button.type = 'button';
      button.setAttribute('aria-label', `放大查看：${photo.caption || photo.alt || '影像'}`);
      button.setAttribute('aria-haspopup', 'dialog');
      const image = element('img');
      image.src = photo.thumbnail || photo.src;
      image.alt = photo.alt;
      image.loading = 'lazy';
      image.decoding = 'async';
      image.width = photo.width;
      image.height = photo.height;
      image.addEventListener('error', () => {
        photoStatus.textContent = '部分影像暂时无法加载，请稍后刷新页面。';
        button.disabled = true;
      }, { once: true });
      const open = element('span', 'photo-open', '↗');
      open.setAttribute('aria-hidden', 'true');
      button.append(image, open);
      button.addEventListener('click', () => openLightbox(index, button));
      const caption = element('figcaption');
      const name = element('span', 'photo-name');
      name.append(element('span', 'photo-number', String(index + 1).padStart(2, '0')), document.createTextNode(photo.caption || photo.alt || '影像'));
      caption.append(name);
      if (photo.credit) caption.append(element('span', 'photo-credit', photo.credit));
      figure.append(button, caption);
      fragment.append(figure);
    });
    photoGrid.replaceChildren(fragment);
    photoStatus.textContent = photoLoadWarning || (announce ? `显示 ${visiblePhotos.length} 张影像` : '');
    revealElements(photoGrid);
  }
  function configurePhotoFilters() {
    const filterGroup = document.querySelector('.photo-filters');
    const categories = new Map([['all', '全部']]);
    photos.forEach(photo => categories.set(photo.category, photo.categoryLabel));
    const fragment = document.createDocumentFragment();
    categories.forEach((label, value) => {
      const button = element('button', '', label);
      button.type = 'button';
      button.dataset.filter = value;
      button.setAttribute('aria-pressed', String(value === 'all'));
      button.addEventListener('click', () => {
        activeFilter = value;
        filterGroup.querySelectorAll('button').forEach(filter => filter.setAttribute('aria-pressed', String(filter === button)));
        renderPhotos(true);
      });
      fragment.append(button);
    });
    activeFilter = 'all';
    filterGroup.replaceChildren(fragment);
  }
  async function hydratePhotos() {
    try {
      const all = await readIndex(photoGrid.dataset.index || 'content/photos/index.json');
      const data = photoGrid.dataset.album ? all.filter(item => item && item.category === photoGrid.dataset.album) : all;
      const directory = photoGrid.dataset.root || 'content/photos/';
      if (!data.length) {
        photos = [];
        photoLoadWarning = '暂无影像。';
      } else {
        photos = data.flatMap(item => {
          if (!item || typeof item.alt !== 'string' || typeof item.caption !== 'string') return [];
          const src = localContentPath(directory, item.file, /\.(?:jpe?g|png|webp|avif|gif|svg)$/i);
          const thumbnail = localContentPath(directory, item.thumbnail, /\.(?:jpe?g|png|webp|avif|gif|svg)$/i);
          const category = typeof item.category === 'string' && item.category.trim() ? item.category.trim() : 'uncategorized';
          const categoryLabel = typeof item.categoryLabel === 'string' ? item.categoryLabel : category;
          const width = Number.isInteger(item.width) && item.width > 0 && item.width <= 20000 ? item.width : 1600;
          const height = Number.isInteger(item.height) && item.height > 0 && item.height <= 20000 ? item.height : 1100;
          return src ? [{ src, thumbnail, alt: item.alt, caption: item.caption, category, categoryLabel, width, height }] : [];
        });
        if (photos.length < data.length) photoLoadWarning = '部分影像条目信息不完整，暂时无法显示。';
      }
    } catch {
      photos = [];
      photoLoadWarning = '影像加载失败，请刷新重试。';
    }
    configurePhotoFilters();
    renderPhotos();
  }
  hydratePhotos();
}
if (document.querySelector('#writing-list')) hydrateWriting();
if (document.querySelector('#photo-grid')) initPhotoGallery();
