'use strict';

const readingProgress = document.querySelector('.reading-progress');
if (readingProgress) {
  let readingFrame = 0;
  function updateReadingProgress() {
    readingFrame = 0;
    const body = document.querySelector('.essay-body');
    const top = body.getBoundingClientRect().top + window.scrollY;
    const distance = Math.max(1, body.offsetHeight - window.innerHeight);
    const progress = Math.max(0, Math.min(1, (window.scrollY - top) / distance));
    readingProgress.style.transform = `scaleX(${progress})`;
  }
  function scheduleReadingProgress() {
    if (!readingFrame) readingFrame = requestAnimationFrame(updateReadingProgress);
  }
  window.addEventListener('scroll', scheduleReadingProgress, { passive: true });
  window.addEventListener('resize', scheduleReadingProgress);
  updateReadingProgress();
}
