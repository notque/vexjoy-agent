/* === Filter Component === */
function setupFilter(inputSelector, itemSelector) {
  const input = document.querySelector(inputSelector);
  input.addEventListener('input', () => {
    const query = input.value.toLowerCase();
    document.querySelectorAll(itemSelector).forEach(item => {
      const text = (item.textContent + ' ' + (item.dataset.keywords || '')).toLowerCase();
      item.classList.toggle('hidden', query && !text.includes(query));
    });
  });
}
function setupTagFilter(barSelector, itemSelector) {
  document.querySelectorAll(barSelector + ' .tag-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll(barSelector + ' .tag-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tag = btn.dataset.tag;
      document.querySelectorAll(itemSelector).forEach(item => {
        item.classList.toggle('hidden', tag !== 'all' && !item.dataset.tags.includes(tag));
      });
    });
  });
}
