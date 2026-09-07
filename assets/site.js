const quotes = [
  { text: 'Ὁ δὲ ἀνεξέταστος βίος οὐ βιωτὸς ἀνθρώπῳ.', source: 'Plato · Apology' },
  { text: 'Cogito, ergo sum.', source: 'René Descartes · Principia Philosophiae' },
  { text: 'Was mich nicht umbringt, macht mich stärker.', source: 'Friedrich Nietzsche · Götzen-Dämmerung' },
  { text: 'Je pense, donc je suis.', source: 'René Descartes · Discours de la méthode' },
  { text: 'Ὅτι οὐ τὰ πράγματα ταράσσει τοὺς ἀνθρώπους, ἀλλὰ τὰ περὶ τῶν πραγμάτων δόγματα.', source: 'Epictetus · Enchiridion' }
];
let quoteIndex = 0;
const quote = document.querySelector('#quote p');
const quoteSource = document.querySelector('#quote cite');
document.querySelector('#quote button').addEventListener('click', () => { quoteIndex = (quoteIndex + 1) % quotes.length; quote.textContent = quotes[quoteIndex].text; quoteSource.textContent = quotes[quoteIndex].source; });

const themeToggle = document.querySelector('.theme-toggle');
function setTheme(theme) { document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme); const dark = theme === 'dark'; themeToggle.setAttribute('aria-pressed', String(dark)); themeToggle.setAttribute('aria-label', dark ? '切换浅色模式' : '切换深色模式'); }
const savedTheme = localStorage.getItem('theme');
setTheme(savedTheme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
themeToggle.addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));

async function loadJson(path, fallback) { try { const response = await fetch(path); return response.ok ? response.json() : fallback; } catch { return fallback; } }
async function hydrateContent() {
  const writing = await loadJson('content/writing/index.json', []);
  document.querySelector('#writing-list').innerHTML = writing.length ? writing.map(item => `<article><time>${item.date}</time><div><h3><a href="content/writing/${item.file}">${item.title}</a></h3><p>${item.summary}</p></div></article>`).join('') : '<p>一些想法，正在酝酿。文章与随笔将在这里更新。</p>';
  const photos = await loadJson('content/photos/index.json', []);
  document.querySelector('#photo-grid').innerHTML = photos.length ? photos.map(item => `<figure><img src="content/photos/${item.file}" alt="${item.alt}"><figcaption>${item.caption}</figcaption></figure>`).join('') : '<p>影像集尚未开始。为下一次按下快门留一个位置。</p>';
}
hydrateContent();
