const quotes = ['在确定与不确定之间，保留一片自由。', '让思考发生，让未完成继续。', '向内寻找，向外生长。'];
let quoteIndex = 0;
const quote = document.querySelector('#quote p');
document.querySelector('#quote button').addEventListener('click', () => { quoteIndex = (quoteIndex + 1) % quotes.length; quote.textContent = quotes[quoteIndex]; });

async function loadJson(path, fallback) { try { const response = await fetch(path); return response.ok ? response.json() : fallback; } catch { return fallback; } }
async function hydrateContent() {
  const writing = await loadJson('content/writing/index.json', []);
  document.querySelector('#writing-list').innerHTML = writing.length ? writing.map(item => `<article><time>${item.date}</time><div><h3><a href="content/writing/${item.file}">${item.title}</a></h3><p>${item.summary}</p></div></article>`).join('') : '<p>一些想法，正在酝酿。文章与随笔将在这里更新。</p>';
  const photos = await loadJson('content/photos/index.json', []);
  document.querySelector('#photo-grid').innerHTML = photos.length ? photos.map(item => `<figure><img src="content/photos/${item.file}" alt="${item.alt}"><figcaption>${item.caption}</figcaption></figure>`).join('') : '<p>影像集尚未开始。为下一次按下快门留一个位置。</p>';
}
hydrateContent();
